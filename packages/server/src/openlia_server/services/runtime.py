"""Build a `ChatRunner` wired to the server's LLM admin settings.

Tests stub this entire factory — the route accepts `chat_runner_factory`
as a parameter so the builder below is only exercised by the running
application. Plan 13 will extend the builder with real tool wiring; for
this blocker the Secretary tool dispatcher returns no tools.

Phase 9.3 adds `run_department(...)` — a single dispatch entry that
picks chat vs deterministic by inspecting the dept's `requires_runner`
plus the caller's mode. Scheduled chat-flow paths (PT, MB cron jobs)
inject a system prompt and run through the chat builder.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from openlia.departments import get_department
from openlia.departments.loader import load_routing_context
from openlia.llm.adapters import build_adapter
from openlia.llm.embeddings import EmbeddingProvider
from openlia.llm.exceptions import ModelNotConfiguredError
from openlia.llm.resolver import resolve, resolve_system_role
from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.recall_artifacts import RecallArtifactsHandler
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.subagent_runner import SubagentReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution, resolve_web_search
from openlia.llm.types import ResolvedModel
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry
from sqlalchemy.orm import Session as DBSession

from openlia_server.runtime_tools.recall_artifacts import build_recall_artifacts_handler
from openlia_server.services.chat_router_client import RouterLlmJsonClient
from openlia_server.services.dispatcher_factory import build_dispatcher
from openlia_server.services.llm_registry import SQLModelRegistry

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM_ROLE_ID = "connector_agentic_resolver"

RuntimeMode = Literal["chat", "deterministic", "scheduled_chat"]


# Slice 12: factory that resolves the user's configured
# ``EmbeddingProvider`` (+ model name). Matches the seam the scheduler
# graph-extraction executor uses so future production wiring can
# share a single resolver. Until the embedding-provider choice is
# persisted (slice-9 wizard step), the default returns a fake provider
# so the rest of the chat path stays exercisable end-to-end.
EmbeddingFactory = Callable[[], tuple[EmbeddingProvider, str]]


def _default_embedding_factory() -> tuple[EmbeddingProvider, str]:
    from openlia.llm.embeddings import FakeEmbeddingProvider

    return FakeEmbeddingProvider(), "fake-embedding"


class _EmptyDataDispatcher:
    """No data-provider tools wired in this blocker. Plan 13 replaces this."""

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return []

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError(f"no data-provider tools registered (attempted {tool_name!r})")

    async def expand_tools(
        self,
        *,
        department_id: str,
        reason: str,
        category_hint: str | None = None,
    ) -> list[dict[str, Any]]:
        return []

    async def available_categories(self) -> list[str]:
        return []


def _resolve_web_search_for(*, resolved: ResolvedModel) -> WebSearchResolution:
    # Native variant is selected when the resolved model advertises
    # `web_search_native=True` and the env-flag kill switch is off.
    # Configured variant requires a connector-backed search adapter;
    # Phase 9 rewires that path, so until then the factory returns None
    # and unsupported-model + native-disabled cases fall through to
    # `available=False`.
    return resolve_web_search(
        resolved=resolved,
        search_adapter_factory=lambda: None,
    )


def select_report_runner_class(
    *, department_id: str
) -> type[ReportRunner] | type[SubagentReportRunner]:
    """Route equity_research to SubagentReportRunner when feature flag set.

    Behind ``OPENLIA_USE_SUBAGENT_RUNNER=1``: equity_research department
    runs through the subagent-architecture report runner. All other
    departments (and the default-off case) keep using the classic
    ``ReportRunner``.
    """
    if os.environ.get("OPENLIA_USE_SUBAGENT_RUNNER") == "1" and department_id == "equity_research":
        return SubagentReportRunner
    return ReportRunner


def _empty_skill_registry() -> SkillRegistry:
    """Return an empty SkillRegistry backed by a temp directory.

    Placeholder until Task 16+ wires the real registry at startup.
    visible() returns [] so skills_menu renders empty.
    """
    _empty_root = Path(tempfile.gettempdir()) / "openlia_skills_empty"
    _empty_root.mkdir(exist_ok=True)
    _empty_fs = FilesystemSkillStore(root=_empty_root)
    return SkillRegistry(store=LayeredSkillStore(system=_empty_fs, user=_empty_fs))


def _build_router_llm_client(db: DBSession) -> RouterLlmJsonClient | None:
    """Resolve a model for the runtime tool router. Returns None when no
    slot default is configured so the caller can fall through to the
    legacy (non-routed) chat path.
    """
    registry = SQLModelRegistry(db)
    try:
        resolved = resolve_system_role(
            role_id=_ROUTER_SYSTEM_ROLE_ID,
            registry=registry,
        )
    except ModelNotConfiguredError as exc:
        logger.warning(
            "no LLM configured for chat tool router; v2 routing disabled (%s)",
            exc,
        )
        return None
    provider = build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )
    return RouterLlmJsonClient(provider=provider)


def _build_chat_runner_with_registry(
    registry: SQLModelRegistry,
    *,
    web_search: WebSearchResolution,
    skill_registry: SkillRegistry | None = None,
    db: DBSession | None = None,
    disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
    recall_artifacts: RecallArtifactsHandler | None = None,
) -> ChatRunner:
    prompts = PromptLoader()

    from openlia_server import dev_events

    def _trace(category: str, message: str, payload: dict[str, Any] | None) -> None:
        dev_events.record(category, message, payload)

    tools = ToolDispatcher(
        data_dispatcher=_EmptyDataDispatcher(),
        web_search=web_search,
        trace=_trace,
    )

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    # v2 wiring: connector dispatcher + tool router + per-dept routing context.
    # Each piece is best-effort; if any fails the runner silently falls back
    # to the legacy v1 path (which has no real data tools, but at least
    # boots cleanly while a misconfigured deploy is being repaired).
    dispatcher = None
    router_llm_client = None
    if db is not None:
        try:
            dispatcher = build_dispatcher(db, disabled_connector_ids=disabled_connector_ids)
        except Exception as exc:
            logger.warning("connector dispatcher build failed; v2 routing disabled: %s", exc)
        router_llm_client = _build_router_llm_client(db)

    return ChatRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
        skill_registry=skill_registry if skill_registry is not None else _empty_skill_registry(),
        trace=_trace,
        dispatcher=dispatcher,
        router_llm_client=router_llm_client,
        routing_context_loader=load_routing_context,
        recall_artifacts=recall_artifacts,
    )


class RefreshingChatRunner:
    """Constructs a fresh ChatRunner (with fresh DB session and registry) per `.run()`.

    Mirrors `RefreshingReportRunner` so a long-running process never reuses a
    DB session across chat turns; the session is opened on entry and closed
    on iterator exhaustion / exception / client-disconnect.
    """

    def __init__(
        self,
        db_session_factory: Callable[[], DBSession],
        skill_registry: SkillRegistry | None = None,
        embedding_factory: EmbeddingFactory | None = None,
    ) -> None:
        self._factory = db_session_factory
        self._skill_registry = skill_registry
        # Slice 12: factory for the embedding provider that powers
        # cross-session report recall. Defaults to the same fake
        # provider the nightly extraction job uses until the user's
        # configured choice is persisted (slice 9 wizard).
        self._embedding_factory: EmbeddingFactory = (
            embedding_factory if embedding_factory is not None else _default_embedding_factory
        )

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
        session_id: str | None = None,
        model_id_override: str | None = None,
        disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
        disabled_skill_ids: frozenset[str] | tuple[str, ...] = (),
        response_length: str | None = None,
        memory_block: str | None = None,
        selected_exemplars: list[str] | None = None,
        market_basket: dict[str, list[str]] | None = None,
    ):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            # Resolve the model up front so web search resolution can
            # consult its capabilities (native variant requires
            # `web_search_native=True`). The runner re-resolves internally
            # on each turn — that's fine since the registry is stable.
            try:
                resolved = resolve(
                    department_id=department_id,
                    user_id=user_id,
                    registry=registry,
                    model_id_override=model_id_override,
                )
                web_search = _resolve_web_search_for(resolved=resolved)
            except ModelNotConfiguredError:
                web_search = WebSearchResolution(False, None, None)
            # Build the recall_artifacts handler with a session factory
            # bound to the same DB the runner uses. The handler opens a
            # fresh session per call so it never reuses a session
            # across turns (matching the per-call pattern used for
            # secretary persistence handlers).
            embed_provider, _embed_model = self._embedding_factory()
            recall_handler = build_recall_artifacts_handler(
                db_session_factory=self._factory,
                provider=embed_provider,
            )
            runner = _build_chat_runner_with_registry(
                registry,
                web_search=web_search,
                skill_registry=self._skill_registry,
                db=db,
                disabled_connector_ids=disabled_connector_ids,
                recall_artifacts=recall_handler,
            )
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                messages=messages,
                attachments=attachments,
                cancel_token=cancel_token,
                session_id=session_id,
                model_id_override=model_id_override,
                disabled_skill_ids=frozenset(disabled_skill_ids),
                response_length=response_length,
                memory_block=memory_block,
                selected_exemplars=selected_exemplars,
                market_basket=market_basket,
            ):
                yield event
        finally:
            db.close()


def build_chat_runner(
    *,
    db_session_factory: Callable[[], DBSession],
    skill_registry: SkillRegistry | None = None,
    embedding_factory: EmbeddingFactory | None = None,
) -> RefreshingChatRunner:
    """Return a refreshing chat runner that opens a fresh DB session per run.

    ``embedding_factory`` resolves the user's embedding provider for the
    cross-session ``recall_artifacts`` tool (slice 12). Defaults to the
    fake provider so the chat path stays bootable before the user has
    configured a real embedding source.
    """
    return RefreshingChatRunner(
        db_session_factory,
        skill_registry=skill_registry,
        embedding_factory=embedding_factory,
    )


def _build_report_runner_with_registry(
    registry: SQLModelRegistry,
    *,
    web_search: WebSearchResolution,
    db: DBSession,
    user_id: str,
    department_id: str,
    run_id: str,
    run_date,
    skill_registry: SkillRegistry | None = None,
    disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
    disabled_skill_ids: tuple[str, ...] | frozenset[str] = (),
) -> ReportRunner | SubagentReportRunner:
    """Build a per-run ``ReportRunner`` wired to the v2 connector dispatcher.

    ``disabled_connector_ids`` and ``disabled_skill_ids`` flow from the
    session row's tool-toggle state; they prune the connector dispatcher
    pool and the skills_menu in the system prompt respectively, matching
    the chat-side contract.
    """
    from openlia_server.services.report_dispatcher_bridge import ReportDispatcherBridge

    prompts = PromptLoader()
    try:
        connector_dispatcher = build_dispatcher(db, disabled_connector_ids=disabled_connector_ids)
    except Exception:
        logger.exception("report runner: build_dispatcher failed; using empty dispatcher")
        data_dispatcher: Any = _EmptyDataDispatcher()
    else:
        data_dispatcher = ReportDispatcherBridge(
            dispatcher=connector_dispatcher,
            department_id=department_id,
        )
    from openlia_server import dev_events

    def _trace(category: str, message: str, payload: dict[str, Any] | None) -> None:
        dev_events.record(category, message, payload)

    tools = ToolDispatcher(
        data_dispatcher=data_dispatcher,
        web_search=web_search,
        trace=_trace,
    )

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    runner_cls = select_report_runner_class(department_id=department_id)
    if runner_cls is SubagentReportRunner:
        # SubagentReportRunner expects resolve(...role=...). The classic
        # resolve() doesn't accept role. Build a role-aware closure that
        # picks the subagent model from env when role=="subagent" and
        # falls back to flagship resolution otherwise.
        def _resolve_with_role(
            *,
            department_id: str,
            user_id: str | None,
            registry,
            role: str = "flagship",
            model_id_override: str | None = None,
        ):
            if role == "subagent":
                sub_model_id = os.environ.get("OPENLIA_DEFAULT_SUBAGENT_MODEL_ID")
                if sub_model_id:
                    row = registry.get_by_id(sub_model_id)
                    if row is not None:
                        from openlia.llm.resolver import _to_resolved

                        return _to_resolved(row)
                # Soft fallback to flagship, warned via dev events.
                _trace(
                    "report.warning.subagent_unconfigured",
                    "subagent model unset or unknown; falling back to flagship.",
                    {"department_id": department_id},
                )
            return resolve(
                department_id=department_id,
                registry=registry,
                user_id=user_id,
                model_id_override=model_id_override,
            )

        return SubagentReportRunner(
            prompts=prompts,
            tools=tools,
            resolve=_resolve_with_role,
            registry=registry,
            flagship_provider_factory=_provider_factory,
            subagent_provider_factory=_provider_factory,
            trace=_trace,
        )
    return ReportRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
        skill_registry=skill_registry if skill_registry is not None else _empty_skill_registry(),
        trace=_trace,
    )


class RefreshingReportRunner:
    """Constructs a fresh ReportRunner (with fresh DB session and registry) per job run."""

    def __init__(
        self,
        db_session_factory: Callable[[], DBSession],
        skill_registry: SkillRegistry | None = None,
    ) -> None:
        self._factory = db_session_factory
        self._skill_registry = skill_registry

    async def run(
        self,
        *,
        department_id: str,
        user_id: str,
        request,
        cancel_token=None,
        attachments=None,
        model_id_override: str | None = None,
        disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
        disabled_skill_ids: tuple[str, ...] | frozenset[str] = (),
    ):
        import uuid as _uuid
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            try:
                resolved = resolve(
                    department_id=department_id,
                    user_id=user_id,
                    registry=registry,
                    model_id_override=model_id_override,
                )
                web_search = _resolve_web_search_for(resolved=resolved)
            except ModelNotConfiguredError:
                web_search = WebSearchResolution(False, None, None)
            run_id = f"r_{_uuid.uuid4().hex[:12]}"
            run_date = _dt.now(_UTC).date()
            runner = _build_report_runner_with_registry(
                registry,
                web_search=web_search,
                skill_registry=self._skill_registry,
                db=db,
                user_id=user_id,
                department_id=department_id,
                run_id=run_id,
                run_date=run_date,
                disabled_connector_ids=disabled_connector_ids,
                disabled_skill_ids=disabled_skill_ids,
            )
            db.commit()
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                request=request,
                cancel_token=cancel_token,
                attachments=attachments,
                model_id_override=model_id_override,
                disabled_skill_ids=frozenset(disabled_skill_ids),
            ):
                yield event
            db.commit()
        finally:
            db.close()


def build_report_runner(
    db_session_factory: Callable[[], DBSession],
    skill_registry: SkillRegistry | None = None,
) -> RefreshingReportRunner:
    return RefreshingReportRunner(db_session_factory, skill_registry=skill_registry)


def _build_batch_runner_with_registry(registry: SQLModelRegistry) -> BatchRunner:
    prompts = PromptLoader()

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    return BatchRunner(
        prompts=prompts,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )


class RefreshingBatchRunner:
    """Constructs a fresh BatchRunner (with fresh DB session) per `.run()`."""

    def __init__(self, db_session_factory: Callable[[], DBSession]) -> None:
        self._factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        task: str,
        items,
        schema,
        concurrency: int = 8,
        user_id: str | None = None,
        cancel_token=None,
    ):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            runner = _build_batch_runner_with_registry(registry)
            return await runner.run(
                department_id=department_id,
                task=task,
                items=items,
                schema=schema,
                concurrency=concurrency,
                user_id=user_id,
                cancel_token=cancel_token,
            )
        finally:
            db.close()


def build_batch_runner(db_session_factory: Callable[[], DBSession]) -> RefreshingBatchRunner:
    return RefreshingBatchRunner(db_session_factory)


# ---- Phase 9.3: single dispatch entry ----


class UnknownDepartmentError(KeyError):
    """Raised when `run_department` cannot resolve `department_id`."""


class RuntimeModeMismatchError(RuntimeError):
    """Caller asked for `deterministic` against a chat-only dept (or vice versa)."""


def select_runtime_mode(*, department_id: str, requested: RuntimeMode | None) -> RuntimeMode:
    """Pick the runtime mode for `department_id`.

    Rules:

      - `requires_runner=True` depts (Macro Research, Retail Sentiment)
        default to deterministic.
      - Chat-only depts (Secretary, Equity Research, Earnings Update,
        Panic Thermometer, Morning Briefing) default to `chat`.
      - Callers may force `scheduled_chat` (PT/MB cron) — that mode is
        always allowed for chat-only depts; rejected for runner depts.

    Raises `UnknownDepartmentError` if the dept is not registered;
    `RuntimeModeMismatchError` if the requested mode contradicts the
    dept's runner requirement.
    """
    dept = get_department(department_id)
    if dept is None:
        raise UnknownDepartmentError(f"unknown department: {department_id!r}")

    requires_runner = bool(getattr(dept, "requires_runner", False))

    if requested is None:
        return "deterministic" if requires_runner else "chat"

    if requested == "deterministic" and not requires_runner:
        raise RuntimeModeMismatchError(
            f"department {department_id!r} is chat-only; cannot run deterministic"
        )
    if requested in ("chat", "scheduled_chat") and requires_runner:
        raise RuntimeModeMismatchError(
            f"department {department_id!r} is a runner; cannot run as chat"
        )
    return requested


def run_department(
    *,
    department_id: str,
    mode: RuntimeMode | None = None,
    request: Any,
    db_session_factory: Callable[[], DBSession],
) -> Any:
    """Single dispatch entry — selects chat vs deterministic.

    Returns whatever the underlying runner returns:

      - `mode == "chat"` or `"scheduled_chat"`: returns an
        `AsyncIterator[SseEvent]` from `RefreshingChatRunner.run(...)`.
        For `scheduled_chat`, `request` must include a `system_prompt`
        attribute / key the orchestration code uses to seed the
        conversation.
      - `mode == "deterministic"`: returns whatever the dept's
        deterministic runner returns. The current MR/RS runners are
        invoked through their existing service entry points; this
        function only resolves the mode and surfaces the chosen runner
        builder so callers can wire it explicitly.

    The bulk of the runner construction still lives in the builders
    above (`build_chat_runner`, etc.); this entry point just picks
    which one to delegate to and propagates the request payload.
    """
    resolved_mode = select_runtime_mode(department_id=department_id, requested=mode)

    if resolved_mode in ("chat", "scheduled_chat"):
        runner = build_chat_runner(db_session_factory=db_session_factory)
        # Scheduled chat path: callers (PT, MB cron jobs) thread a
        # `system_prompt` and a single user-role seed message into the
        # request. The chat runner consumes the same `messages` shape
        # as the live route, so no special-casing is needed beyond
        # the mode selection itself.
        return runner.run(
            department_id=department_id,
            user_id=getattr(request, "user_id", None),
            messages=getattr(request, "messages", []),
            attachments=getattr(request, "attachments", None),
            cancel_token=getattr(request, "cancel_token", None),
        )

    # Deterministic mode — surface the dispatcher-aware builder. The
    # MR/RS scheduler executors call their own service entry points
    # (mr_runner / rs_runner), so this branch returns the request back
    # to the caller along with the resolved mode for transparency.
    # Callers should construct the runner themselves; this entry point
    # exists primarily to validate mode selection and to give the
    # scheduler a single place to ask "should I run chat or
    # deterministic?" before dispatching.
    return {"mode": resolved_mode, "request": request, "department_id": department_id}
