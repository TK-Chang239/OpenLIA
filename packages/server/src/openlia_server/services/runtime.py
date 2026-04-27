"""Build a `ChatRunner` wired to the server's LLM admin settings.

Tests stub this entire factory — the route accepts `chat_runner_factory`
as a parameter so the builder below is only exercised by the running
application. Plan 13 will extend the builder with real tool wiring; for
this blocker the Secretary tool dispatcher returns no tools.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlia.connectors.dispatch import Dispatcher
from openlia.data.adapters import ADAPTERS
from openlia.data.types import ProviderCategory
from openlia.llm.adapters import build_adapter
from openlia.llm.resolver import resolve
from openlia.llm.runtime.batch import BatchRunner
from openlia.llm.runtime.chat import ChatRunner
from openlia.llm.runtime.prompts import PromptLoader
from openlia.llm.runtime.report import ReportRunner
from openlia.llm.runtime.tools import ToolDispatcher
from openlia.llm.runtime.web_search import WebSearchAdapter, WebSearchResolution
from sqlalchemy.orm import Session as DBSession

from openlia_server.services import data_providers as dp_svc
from openlia_server.services.dispatcher_factory import build_dispatcher_for_session
from openlia_server.services.llm_registry import SQLModelRegistry


class _EmptyDataDispatcher:
    """No data-provider tools wired in this blocker. Plan 13 replaces this."""

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return []

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        raise RuntimeError(f"no data-provider tools registered (attempted {tool_name!r})")

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None:
        return None


def _resolve_configured_search(db: DBSession) -> WebSearchResolution:
    """Pick the highest-priority enabled SEARCH provider and wrap it as a
    WebSearchResolution. Returns an unavailable resolution if none configured.

    Priority is read from `extra_config.default_priority` (lower wins, default 100),
    matching the wizard convention. When no SEARCH provider is configured or the
    chosen one fails to instantiate, returns an unavailable resolution so the
    runtime omits the `web_search` tool.
    """
    rows = [
        r
        for r in dp_svc.list_providers_by_category(db, category=ProviderCategory.SEARCH)
        if r.is_enabled
    ]
    if not rows:
        return WebSearchResolution(available=False, variant=None, adapter=None)
    rows.sort(key=lambda r: int((r.extra_config or {}).get("default_priority", 100)))
    for row in rows:
        adapter_cls = ADAPTERS.get(row.kind)
        if adapter_cls is None:
            continue
        try:
            entry = dp_svc.load_provider_entry(db, row.id)
            adapter = adapter_cls(entry)
        except Exception:
            continue
        if not isinstance(adapter, WebSearchAdapter):
            continue
        return WebSearchResolution(available=True, variant="configured", adapter=adapter)
    return WebSearchResolution(available=False, variant=None, adapter=None)


def _build_chat_runner_with_registry(
    registry: SQLModelRegistry,
    *,
    dispatcher: Dispatcher,
    web_search: WebSearchResolution | None = None,
) -> ChatRunner:
    # `web_search` is retained for signature compatibility with existing
    # call sites (and tests that monkey-patch this factory) but is no
    # longer consumed: the new connector dispatcher handles search-tool
    # gating via `Category.WEB_SEARCH` allowlist filtering.
    del web_search
    prompts = PromptLoader()

    def _provider_factory(resolved):
        return build_adapter(
            kind=resolved.provider_kind,
            credentials=resolved.credentials,
            model=resolved.model_ref,
            capabilities=resolved.capabilities,
        )

    return ChatRunner(
        prompts=prompts,
        dispatcher=dispatcher,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )


class RefreshingChatRunner:
    """Constructs a fresh ChatRunner (with fresh DB session and registry) per `.run()`.

    Mirrors `RefreshingReportRunner` so a long-running process never reuses a
    DB session across chat turns; the session is opened on entry and closed
    on iterator exhaustion / exception / client-disconnect.
    """

    def __init__(self, db_session_factory: Callable[[], DBSession]) -> None:
        self._factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        messages,
        attachments=None,
        cancel_token=None,
    ):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            dispatcher = build_dispatcher_for_session(db)
            runner = _build_chat_runner_with_registry(registry, dispatcher=dispatcher)
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                messages=messages,
                attachments=attachments,
                cancel_token=cancel_token,
            ):
                yield event
        finally:
            db.close()


def build_chat_runner(
    *,
    db_session_factory: Callable[[], DBSession],
) -> RefreshingChatRunner:
    """Return a refreshing chat runner that opens a fresh DB session per run."""
    return RefreshingChatRunner(db_session_factory)


def _build_report_runner_with_registry(
    registry: SQLModelRegistry,
    *,
    web_search: WebSearchResolution,
) -> ReportRunner:
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

    return ReportRunner(
        prompts=prompts,
        tools=tools,
        resolve=resolve,
        registry=registry,
        provider_factory=_provider_factory,
    )


class RefreshingReportRunner:
    """Constructs a fresh ReportRunner (with fresh DB session and registry) per job run."""

    def __init__(self, db_session_factory: Callable[[], DBSession]) -> None:
        self._factory = db_session_factory

    async def run(
        self,
        *,
        department_id: str,
        user_id: str,
        request,
        cancel_token=None,
    ):
        db = self._factory()
        try:
            registry = SQLModelRegistry(db)
            web_search = _resolve_configured_search(db)
            runner = _build_report_runner_with_registry(registry, web_search=web_search)
            async for event in runner.run(
                department_id=department_id,
                user_id=user_id,
                request=request,
                cancel_token=cancel_token,
            ):
                yield event
        finally:
            db.close()


def build_report_runner(db_session_factory: Callable[[], DBSession]) -> RefreshingReportRunner:
    return RefreshingReportRunner(db_session_factory)


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
