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
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from openlia.departments import get_department
from openlia.departments.loader import load_routing_context
from openlia.llm.adapters import build_adapter
from openlia.llm.exceptions import TierNotConfiguredError
from openlia.llm.resolver import resolve
from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ModelTier
from openlia.skills import FilesystemSkillStore, LayeredSkillStore, SkillRegistry
from sqlalchemy.orm import Session as DBSession

from openlia_server.services.chat_router_client import RouterLlmJsonClient
from openlia_server.services.dispatcher_factory import build_dispatcher
from openlia_server.services.llm_registry import SQLModelRegistry

logger = logging.getLogger(__name__)

# Tier the runtime tool router asks for; falls back through these in order
# so a partial install (only Everyday or Thinking configured) still routes.
_ROUTER_TIERS: tuple[ModelTier, ...] = (
    ModelTier.QUICK,
    ModelTier.EVERYDAY,
    ModelTier.THINKING,
)
_ROUTER_DEPARTMENT_ID = "_chat_router"

RuntimeMode = Literal["chat", "deterministic", "scheduled_chat"]


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


def _resolve_configured_search(db: DBSession) -> WebSearchResolution:
    # Stub during connector-v2 rebuild; Phase 9 rewires search through the
    # connector dispatcher.
    return WebSearchResolution(available=False, variant=None, adapter=None)


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
    tier is configured so the caller can fall through to the legacy
    (non-routed) chat path.
    """
    registry = SQLModelRegistry(db)
    last_error: TierNotConfiguredError | None = None
    for tier in _ROUTER_TIERS:
        try:
            resolved = resolve(
                department_id=_ROUTER_DEPARTMENT_ID,
                registry=registry,
                user_id=None,
                tier_override=tier,
            )
        except TierNotConfiguredError as exc:
            last_error = exc
            continue
        provider = build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )
        return RouterLlmJsonClient(provider=provider)
    logger.warning(
        "no LLM tier configured for chat tool router; v2 routing disabled (%s)",
        last_error,
    )
    return None


def _build_chat_runner_with_registry(
    registry: SQLModelRegistry,
    *,
    web_search: WebSearchResolution,
    skill_registry: SkillRegistry | None = None,
    db: DBSession | None = None,
    disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
) -> ChatRunner:
    prompts = PromptLoader()
    tools = ToolDispatcher(
        data_dispatcher=_EmptyDataDispatcher(),
        web_search=web_search,
    )

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    from openlia_server import dev_events

    def _trace(category: str, message: str, payload: dict[str, Any] | None) -> None:
        dev_events.record(category, message, payload)

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
    ) -> None:
        self._factory = db_session_factory
        self._skill_registry = skill_registry

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
    ):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            web_search = _resolve_configured_search(db)
            runner = _build_chat_runner_with_registry(
                registry,
                web_search=web_search,
                skill_registry=self._skill_registry,
                db=db,
                disabled_connector_ids=disabled_connector_ids,
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
            ):
                yield event
        finally:
            db.close()


def build_chat_runner(
    *,
    db_session_factory: Callable[[], DBSession],
    skill_registry: SkillRegistry | None = None,
) -> RefreshingChatRunner:
    """Return a refreshing chat runner that opens a fresh DB session per run."""
    return RefreshingChatRunner(db_session_factory, skill_registry=skill_registry)


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
) -> ReportRunner:
    """Build a per-run ``ReportRunner`` wired to the v2 connector dispatcher.

    The bridge instance is pinned to ``(user_id, department_id, run_id,
    run_date)`` so usage records the right cache row. ``RefreshingReportRunner``
    creates a fresh ``ReportRunner`` per call so this binding is safe.
    """
    from openlia_server.services.report_dispatcher_bridge import ReportDispatcherBridge
    from openlia_server.services.report_tool_cache import ReportToolCache

    prompts = PromptLoader()
    cache = ReportToolCache(session=db)
    cache.note_run_started(
        user_id=user_id,
        department_id=department_id,
        run_id=run_id,
        run_date=run_date,
    )
    try:
        connector_dispatcher = build_dispatcher(db)
    except Exception:
        logger.exception("report runner: build_dispatcher failed; using empty dispatcher")
        data_dispatcher: Any = _EmptyDataDispatcher()
    else:
        data_dispatcher = ReportDispatcherBridge(
            dispatcher=connector_dispatcher,
            cache=cache,
            user_id=user_id,
            department_id=department_id,
            run_id=run_id,
            run_date=run_date,
        )
    tools = ToolDispatcher(
        data_dispatcher=data_dispatcher,
        web_search=web_search,
    )

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    from openlia_server import dev_events

    def _trace(category: str, message: str, payload: dict[str, Any] | None) -> None:
        dev_events.record(category, message, payload)

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
    ):
        import uuid as _uuid
        from datetime import UTC as _UTC
        from datetime import datetime as _dt

        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            web_search = _resolve_configured_search(db)
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
            )
            db.commit()
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                request=request,
                cancel_token=cancel_token,
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
