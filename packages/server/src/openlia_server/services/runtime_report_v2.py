"""WavedReportRunnerHost — adapts WavedReportRunner to the RefreshingReportRunner contract.

Called when ``OPENLIA_REPORT_V2_ENABLED=true`` and ``department_id == "equity_research"``.

Adapter seams
-------------
- ``dispatcher`` shim: ``WavedReportRunner`` expects
  ``ToolDispatcher(Protocol)`` from ``manifest/baseline.py`` — a single
  ``async def dispatch(provider, tool, args) -> Any``.  We bridge to the
  v2 connector ``Dispatcher.dispatch_tool_use`` which takes a
  ``provider__tool`` prefixed name.

- ``websearch`` shim: aggregator expects ``WebSearchProvider(Protocol)``
  with ``async def search(query) -> list[dict]``.  We adapt the
  existing ``WebSearchResolution.adapter`` (configured variant) or return
  empty results for native (the v2 runner handles native search at the
  facts-pack level, not via a search adapter).

- ``body_writer`` / ``synthesis_writer``: ``ProviderSectionWriter`` wraps
  the flagship ``LLMProvider``.

- ``preflight_provider``: ``ProviderStructuredOutput`` wraps a lighter
  model resolved from ``OPENLIA_REPORT_V2_PREFLIGHT_MODEL_ID`` env var;
  falls back to the flagship when unset.

- SSE bridging: ``WavedReportRunner.run()`` returns ``ReportRunOutput``
  and emits events via the optional ``sse_emitter`` async callable.  This
  host bridges that callback into the async-generator contract that
  ``RefreshingReportRunner`` yields.

Stubs / gaps (deferred to Task 6.4 smoke)
------------------------------------------
- ``model_id_override``, ``disabled_connector_ids``, ``disabled_skill_ids``
  are accepted but not forwarded (v2 runner has no skip-section concept
  yet).  ``cancel_token`` is not forwarded (WavedReportRunner has no
  cancellation hook yet).
- ``attachments`` are silently ignored (v2 runner does not accept docs yet).
- The ``ReportComplete.schema`` event is emitted by ``WavedReportRunner``
  itself; this host passes it through without the token-cost fields that
  the v1 runner adds.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.runtime.events import SseEvent
from openlia.llm.runtime.messages import ReportRequest
from openlia.llm.runtime.report_v2.runner import WavedReportRunner
from openlia.llm.runtime.report_v2.writers import (
    ProviderSectionWriter,
    ProviderStructuredOutput,
)
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import ResolvedModel

from openlia_server.services.llm_registry import SQLModelRegistry

log = logging.getLogger(__name__)

# ---- Dispatcher shim -------------------------------------------------------


class _V2DispatcherShim:
    """Adapts ``openlia.connectors.dispatch.Dispatcher`` to the
    ``ToolDispatcher`` Protocol expected by ``manifest/baseline.py``.

    The v2 connector dispatcher uses ``provider__tool`` prefixed names,
    e.g. ``eodhd__get_fundamentals_data``.  The manifest baseline calls
    ``dispatch(provider, tool, args)`` — this shim joins them.
    """

    def __init__(self, dispatcher: Any) -> None:
        self._dispatcher = dispatcher

    async def dispatch(self, provider: str, tool: str, args: dict[str, Any]) -> Any:
        prefixed = f"{provider}__{tool}"
        return await self._dispatcher.dispatch_tool_use(prefixed, args)


class _NullDispatcherShim:
    """Fallback when no connector dispatcher is available.

    Every call raises so the ``run_baseline`` gather treats it as a
    failed fetch (payload=None) and continues with an empty manifest.
    """

    async def dispatch(self, provider: str, tool: str, args: dict[str, Any]) -> Any:
        raise RuntimeError(f"no connector dispatcher available; cannot dispatch {provider}__{tool}")


# ---- WebSearch shim ---------------------------------------------------------


class _WebSearchShim:
    """Adapts ``WebSearchResolution`` to the ``WebSearchProvider`` Protocol.

    ``configured`` variant: delegates to ``resolution.adapter.search``.
    ``native`` / ``unavailable``: returns empty list (native search is
    handled by provider adapters at the LLM level, not here).
    """

    def __init__(self, resolution: WebSearchResolution) -> None:
        self._resolution = resolution

    async def search(self, query: str) -> list[dict[str, Any]]:
        if self._resolution.available and self._resolution.variant == "configured":
            adapter = self._resolution.adapter
            if adapter is not None:
                results = await adapter.search(query)
                return [{"title": r.title, "url": r.url, "snippet": r.snippet} for r in results]
        return []


# ---- Provider helpers -------------------------------------------------------


def _provider_from_resolved(resolved: ResolvedModel) -> Any:
    return build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=resolved.capabilities,
    )


def _resolve_preflight(
    *,
    registry: SQLModelRegistry,
    flagship_resolved: ResolvedModel,
    user_id: str,
) -> ResolvedModel:
    """Try to resolve a cheap model for preflight structured output.

    Order:
    1. ``OPENLIA_REPORT_V2_PREFLIGHT_MODEL_ID`` env var — explicit model row id.
    2. Fall back to flagship (same model as body/synthesis).
    """
    preflight_id = os.environ.get("OPENLIA_REPORT_V2_PREFLIGHT_MODEL_ID")
    if preflight_id:
        row = registry.get_by_id(preflight_id)
        if row is not None:
            from openlia.llm.resolver import _to_resolved

            return _to_resolved(row)
        log.warning(
            "OPENLIA_REPORT_V2_PREFLIGHT_MODEL_ID=%r not found in registry; "
            "falling back to flagship for preflight",
            preflight_id,
        )
    return flagship_resolved


# ---- Host class -------------------------------------------------------------


class WavedReportRunnerHost:
    """Adapts ``WavedReportRunner`` to the ``ReportRunner`` constructor/run interface.

    Constructor matches the shape used by ``_build_report_runner_with_registry``
    when ``runner_cls is SubagentReportRunner`` — takes ``prompts``, ``tools``,
    ``resolve``, ``registry``, ``flagship_provider_factory``,
    ``subagent_provider_factory``, and ``trace``.  We accept ``**kwargs``
    for any extra kwargs the caller may pass (e.g. ``skill_registry``).

    The ``run()`` signature mirrors ``ReportRunner.run()`` so
    ``RefreshingReportRunner`` can call it as an async generator.
    """

    # Accept the same constructor kwargs as SubagentReportRunner so
    # _build_report_runner_with_registry can instantiate us without changes.
    def __init__(
        self,
        *,
        prompts: Any,
        tools: Any,
        resolve: Any,
        registry: Any,
        flagship_provider_factory: Any = None,
        subagent_provider_factory: Any = None,
        provider_factory: Any = None,
        trace: Any = None,
        **kwargs: Any,
    ) -> None:
        # Normalise: SubagentReportRunner uses flagship_provider_factory,
        # ReportRunner uses provider_factory — accept both.
        self._provider_factory = flagship_provider_factory or provider_factory
        self._registry = registry
        self._resolve = resolve
        self._trace = trace
        self._tools = tools  # ToolDispatcher (carries the v2 connector dispatcher inside)

    async def run(
        self,
        *,
        department_id: str,
        user_id: str,
        request: ReportRequest,
        cancel_token: Any = None,
        attachments: Any = None,
        model_id_override: str | None = None,
        disabled_connector_ids: tuple[str, ...] | frozenset[str] = (),
        disabled_skill_ids: tuple[str, ...] | frozenset[str] = (),
        sse_emitter: Any = None,
        run_id: str | None = None,
        language: str | None = None,
    ):
        """Async generator that mirrors the ReportRunner.run() contract.

        Instantiates ``WavedReportRunner``, bridges its ``sse_emitter``
        callback into yielded events, and returns after ``runner.run()``
        completes (or raises).

        Stubs / gaps
        ------------
        - ``cancel_token`` — not forwarded; WavedReportRunner has no
          cancellation hook yet (Task 6.4).
        - ``attachments`` — silently ignored; v2 runner does not accept
          file attachments yet.
        - ``disabled_connector_ids`` / ``disabled_skill_ids`` — accepted
          but not forwarded; v2 runner has no skip-section concept yet.
        - ``model_id_override`` — accepted but not forwarded; v2 runner
          resolves the model at the writer level, not per-call yet.
        """
        # 1. Extract ticker from user_input (equity research convention:
        #    user_input IS the ticker symbol, e.g. "AAPL").
        ticker = (request.user_input or "").strip().upper()
        if not ticker:
            raise ValueError(
                "WavedReportRunnerHost: request.user_input is empty; "
                "cannot determine ticker for WavedReportRunner"
            )

        # 2. Resolve flagship model.
        from openlia.llm.exceptions import ModelNotConfiguredError

        try:
            flagship_resolved = self._resolve(
                department_id=department_id,
                user_id=user_id,
                registry=self._registry,
                model_id_override=model_id_override,
            )
        except ModelNotConfiguredError as exc:
            raise RuntimeError(
                f"WavedReportRunnerHost: no LLM configured for {department_id!r}: {exc}"
            ) from exc

        flagship_provider = self._provider_factory(flagship_resolved)

        # 3. Resolve preflight model (cheap structured-output model).
        preflight_resolved = _resolve_preflight(
            registry=self._registry,
            flagship_resolved=flagship_resolved,
            user_id=user_id,
        )
        preflight_provider = self._provider_factory(preflight_resolved)

        # 4. Build web search shim from ToolDispatcher's web_search resolution.
        #    ToolDispatcher stores its WebSearchResolution as _web_search.
        web_search_resolution: WebSearchResolution | None = getattr(
            self._tools, "_web_search", None
        )
        if web_search_resolution is None:
            web_search_resolution = WebSearchResolution(available=False, variant=None, adapter=None)
        websearch_shim = _WebSearchShim(web_search_resolution)

        # 5. Build connector dispatcher shim.
        #    ToolDispatcher stores its DataProviderDispatcher as ``_data``
        #    (see core/llm/runtime/tools.py:367). The real v2 connector
        #    Dispatcher is inside ReportDispatcherBridge as ``.dispatcher``.
        data_dispatcher = getattr(self._tools, "_data", None)
        if data_dispatcher is not None and hasattr(data_dispatcher, "dispatcher"):
            # ReportDispatcherBridge — unwrap the inner Dispatcher.
            dispatcher_shim: Any = _V2DispatcherShim(data_dispatcher.dispatcher)
        elif data_dispatcher is not None and hasattr(data_dispatcher, "dispatch_tool_use"):
            # Bare Dispatcher (unlikely but safe).
            dispatcher_shim = _V2DispatcherShim(data_dispatcher)
        else:
            log.warning(
                "WavedReportRunnerHost: no v2 connector dispatcher found; "
                "baseline fetches will fail gracefully"
            )
            dispatcher_shim = _NullDispatcherShim()

        # 6. Build section writers.
        body_writer = ProviderSectionWriter(
            provider=flagship_provider,
            resolved_model=flagship_resolved,
            max_tokens=8192,
        )
        synthesis_writer = ProviderSectionWriter(
            provider=flagship_provider,
            resolved_model=flagship_resolved,
            max_tokens=8192,
        )
        preflight_writer = ProviderStructuredOutput(
            provider=preflight_provider,
            resolved_model=preflight_resolved,
            max_tokens=4096,
        )

        # 7. Bridge WavedReportRunner's sse_emitter callback into yielded
        #    SSE events via an asyncio.Queue.
        event_queue: asyncio.Queue[SseEvent | None] = asyncio.Queue()

        async def _emit(event: SseEvent) -> None:
            await event_queue.put(event)

        runner = WavedReportRunner(
            report_type="stock_initiation",
            ticker=ticker,
            dispatcher=dispatcher_shim,
            websearch=websearch_shim,
            preflight_provider=preflight_writer,
            body_writer=body_writer,
            synthesis_writer=synthesis_writer,
            sse_emitter=_emit,
            report_id=run_id,
            language=language,
        )

        # Run the WavedReportRunner concurrently and drain the event queue.
        runner_task = asyncio.create_task(runner.run())

        # Drain events while the runner is active.
        while not runner_task.done():
            try:
                event = event_queue.get_nowait()
                yield event
            except asyncio.QueueEmpty:
                # Yield control so the runner can make progress.
                await asyncio.sleep(0)

        # Drain any remaining events after runner finishes.
        while not event_queue.empty():
            try:
                event = event_queue.get_nowait()
                yield event
            except asyncio.QueueEmpty:
                break

        # Re-raise any exception from the runner task.
        runner_task.result()
