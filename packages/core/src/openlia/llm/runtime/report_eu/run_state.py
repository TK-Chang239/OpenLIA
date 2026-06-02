"""Step-wise EU v2 run state for the batch orchestrator.

The live ``Runner`` drives an inline loop that calls ``session.generate``
each turn. The batch path can't call generate inline — every turn round-
trips through the provider Batch API. ``EuRunState`` externalizes that one
call: it owns all the per-run state the runner builds (catalog, system
prompt, message history, workspace, ledger) and exposes the loop body as
two steps the orchestrator drives:

  - ``pending_request()`` -> the next ``LLMRequest`` (or ``None`` when the
    run is terminal). Built identically to ``LLMSession.generate``'s
    request (system, tools, native tools, max_tokens incl. reasoning
    overhead, temperature, cache_conversation).
  - ``apply_response(response)`` -> ingest one model turn: web citations,
    assistant message, tool dispatch, finalize/limit check, web-citation
    notice. Async because EU tools include async connector tools.

It reuses the runner's free functions (``_initial_user_turn``,
``_connector_prompt_info``, ``_dispatch_one``, ``_finish``) so the tool
dispatch and finalize semantics stay identical — the live runner is left
untouched. Scheduled batch runs have no SSE client, so terminal events go
to a ``NullEmitter``.
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

from ...capabilities import capabilities_for
from ...types import LLMRequest, LLMResponse, Message, ReasoningEffort, ToolCall
from .events import NullEmitter
from .ledger import CitationLedger
from .prompts import build_system_prompt
from .runner import (
    _connector_prompt_info,
    _dispatch_one,
    _finish,
    _initial_user_turn,
)
from .schemas import (
    ChartSpec,
    CoverSpec,
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
    RunResult,
    TemplateSpec,
    TriggerContext,
)
from .session import _REASONING_OVERHEAD
from .tools import build_catalog
from .tools.web_search import format_web_citation_notice, ingest_web_citations
from .transports import EuDataTransports
from .workspace import RunWorkspace, WrittenSection

# Mirrors Runner's default hard cap on model turns.
_DEFAULT_MAX_TURNS = 60

_NO_TOOL_FAILURE = (
    "Model ended turn without calling any tool and without calling "
    "finalize(). Likely the run was truncated or the prompt was "
    "misunderstood."
)


@dataclass
class EuRunState:
    """One EU v2 run, driven a turn at a time by the batch orchestrator."""

    request: RunRequest
    custom_id: str
    workspace: RunWorkspace
    ledger: CitationLedger
    tools_by_name: dict[str, Any]
    tool_schemas: list
    native_tools: tuple[str, ...]
    system_prompt: str
    max_output_tokens: int
    messages: list[Message]
    max_turns: int = _DEFAULT_MAX_TURNS
    turn: int = 0
    # Optional connector dispatcher (duck-typed: async ``in_department``
    # context manager). When set, tool dispatch runs inside its context so
    # connector tools resolve per-department credentials. Only tool
    # execution needs it — the model call happens remotely via the batch.
    dispatcher: Any = None
    _result: RunResult | None = field(default=None, repr=False)

    @classmethod
    def from_request(
        cls,
        request: RunRequest,
        *,
        transports: EuDataTransports,
        custom_id: str,
        dispatcher: Any = None,
        max_turns: int = _DEFAULT_MAX_TURNS,
    ) -> EuRunState:
        """Build a fresh run state — mirrors ``Runner.run``'s setup."""
        ledger = CitationLedger()
        workspace = RunWorkspace(
            template=request.template,
            ledger=ledger,
            subject=request.subject,
        )
        catalog = build_catalog(
            ledger=ledger,
            workspace=workspace,
            transports=transports,
            enabled_connectors=request.enabled_connectors,
            dispatcher=dispatcher,
        )
        system_prompt = build_system_prompt(
            request, connector_tools=_connector_prompt_info(catalog)
        )
        caps = capabilities_for(provider_kind=request.provider_kind, model=request.model)
        return cls(
            request=request,
            custom_id=custom_id,
            workspace=workspace,
            ledger=ledger,
            tools_by_name=catalog.by_name(),
            tool_schemas=catalog.core_schemas(),
            native_tools=catalog.native_tools,
            system_prompt=system_prompt,
            max_output_tokens=caps.max_output_tokens,
            messages=[_initial_user_turn(request)],
            max_turns=max_turns,
            dispatcher=dispatcher,
        )

    @property
    def terminal(self) -> bool:
        return self._result is not None

    def pending_request(self) -> LLMRequest | None:
        """The next request to submit, or None once the run is terminal."""
        if self._result is not None:
            return None
        if self.turn >= self.max_turns:
            self._result = _finish(
                self.workspace,
                NullEmitter(),
                status="failed",
                message=(
                    f"EU v2 run hit hard limit of {self.max_turns} model turns "
                    f"without calling finalize(). Partial work preserved."
                ),
            )
            return None
        effective_max = self.max_output_tokens
        if self.request.reasoning_effort is not None:
            effective_max += _REASONING_OVERHEAD.get(self.request.reasoning_effort, 0)
        return LLMRequest(
            messages=list(self.messages),
            system=self.system_prompt,
            tools=self.tool_schemas,
            native_tools=self.native_tools,
            max_tokens=effective_max,
            temperature=0.4,
            reasoning_effort=self.request.reasoning_effort,
            # Multi-turn tool-use loop: cache the growing prefix (no-op when
            # batch turns land past the cache TTL, but free when they don't).
            cache_conversation=True,
        )

    async def apply_response(self, response: LLMResponse) -> None:
        """Ingest one model turn. Mirrors one iteration of Runner's loop."""
        if self._result is not None:
            return

        web_citation_rewrites: dict[str, str] = {}
        if self.request.enabled_connectors.web_search:
            web_citation_rewrites = ingest_web_citations(response.citations, self.ledger)

        self.messages.append(
            Message(
                role="assistant",
                content=response.text or "",
                tool_calls=tuple(response.tool_calls),
            )
        )

        if not response.tool_calls:
            if self.workspace.finalized:
                self._result = _finish(self.workspace, NullEmitter(), status="completed")
            else:
                self._result = _finish(
                    self.workspace,
                    NullEmitter(),
                    status="failed",
                    message=_NO_TOOL_FAILURE,
                )
            return

        if self.dispatcher is not None:
            ctx = self.dispatcher.in_department("earnings_update")
        else:
            ctx = contextlib.nullcontext()
        async with ctx:
            for call in response.tool_calls:
                result_message = await _dispatch_one(call, self.tools_by_name)
                self.messages.append(result_message)

        if self.workspace.finalized:
            self._result = _finish(self.workspace, NullEmitter(), status="completed")
            return

        if self.request.enabled_connectors.web_search:
            notice = format_web_citation_notice(response.citations, web_citation_rewrites)
            if notice is not None:
                self.messages.append(Message(role="user", content=notice))

        self.turn += 1

    def result(self) -> RunResult | None:
        return self._result

    def snapshot(self) -> dict:
        """Serialize the resumable state to a JSON-able dict.

        Captures everything ``restore`` needs to rebuild an equivalent run:
        the request (to rebuild catalog/system prompt/capabilities), the full
        message history, the workspace's produced state, the ledger entries,
        and the turn counter. Catalog/tool schemas are NOT stored — they are
        deterministic functions of the request and get rebuilt on restore.
        """
        ws = self.workspace
        return {
            "custom_id": self.custom_id,
            "max_turns": self.max_turns,
            "turn": self.turn,
            "request": _serialize_request(self.request),
            "messages": [_serialize_message(m) for m in self.messages],
            "workspace": {
                "sections": [
                    {"section_id": s.section_id, "title": s.title, "markdown": s.markdown}
                    for s in ws.sections.values()
                ],
                "section_order": list(ws.section_order),
                "charts": [c.model_dump(mode="json") for c in ws.charts.values()],
                "finalized": ws.finalized,
                "sections_written_this_run": sorted(ws.sections_written_this_run),
                "charts_written_this_run": sorted(ws.charts_written_this_run),
                "cover": ws.cover.model_dump(mode="json") if ws.cover is not None else None,
                "cover_written_this_run": ws.cover_written_this_run,
            },
            "ledger": [e.model_dump(mode="json") for e in self.ledger.all()],
        }

    @classmethod
    def restore(
        cls,
        snapshot: dict,
        *,
        transports: EuDataTransports,
        dispatcher: Any = None,
    ) -> EuRunState:
        """Rebuild a run from a ``snapshot``.

        Rebuilds the catalog / system prompt / capabilities from the stored
        request (via ``from_request``), then overwrites the message history,
        turn, workspace produced-state, and ledger in place — so the catalog
        tools (which hold references to the same workspace + ledger) see the
        restored state.
        """
        request = _deserialize_request(snapshot["request"])
        state = cls.from_request(
            request,
            transports=transports,
            dispatcher=dispatcher,
            custom_id=snapshot["custom_id"],
            max_turns=snapshot["max_turns"],
        )
        state.turn = snapshot["turn"]
        state.messages = [_deserialize_message(m) for m in snapshot["messages"]]

        ws_snap = snapshot["workspace"]
        ws = state.workspace
        ws.sections = {
            s["section_id"]: WrittenSection(
                section_id=s["section_id"], title=s["title"], markdown=s["markdown"]
            )
            for s in ws_snap["sections"]
        }
        ws.section_order = list(ws_snap["section_order"])
        ws.charts = {c["chart_id"]: ChartSpec.model_validate(c) for c in ws_snap["charts"]}
        ws.finalized = ws_snap["finalized"]
        ws.sections_written_this_run = set(ws_snap["sections_written_this_run"])
        ws.charts_written_this_run = set(ws_snap["charts_written_this_run"])
        ws.cover = CoverSpec.model_validate(ws_snap["cover"]) if ws_snap["cover"] else None
        ws.cover_written_this_run = ws_snap["cover_written_this_run"]

        # Seed the (fresh, empty) ledger the catalog tools reference.
        state.ledger.seed(snapshot["ledger"])
        return state


def _serialize_message(m: Message) -> dict:
    return {
        "role": m.role,
        "content": m.content,
        "tool_call_id": m.tool_call_id,
        "tool_calls": [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in m.tool_calls
        ],
    }


def _deserialize_message(data: dict) -> Message:
    return Message(
        role=data["role"],
        content=data["content"],
        tool_call_id=data.get("tool_call_id"),
        tool_calls=tuple(
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in data.get("tool_calls", [])
        ),
    )


def _serialize_request(request: RunRequest) -> dict:
    return request.model_dump(mode="json")


def _restore_template(data: dict) -> TemplateSpec:
    """Rebuild a TemplateSpec, tolerating the freeform spec.

    The freeform template is built via ``model_construct`` (sections=[]
    violates ``min_length=1``), so a plain ``model_validate`` would reject a
    freeform dump. Fall back to ``model_construct`` for that case.
    """
    try:
        return TemplateSpec.model_validate(data)
    except Exception:  # pydantic ValidationError on the freeform (empty-sections) spec
        return TemplateSpec.model_construct(**data)


def _deserialize_request(data: dict) -> RunRequest:
    """Rebuild a RunRequest from its JSON dump.

    Sub-models are validated individually, then assembled via
    ``model_construct`` so the (already-typed) freeform template doesn't trip
    RunRequest's recursive validation.
    """
    trigger = data.get("trigger_context")
    reasoning = data.get("reasoning_effort")
    return RunRequest.model_construct(
        subject=data["subject"],
        template=_restore_template(data["template"]),
        language=Language(data["language"]),
        length=ReportLength(data["length"]),
        provider_kind=data["provider_kind"],
        model=data["model"],
        reasoning_effort=ReasoningEffort(reasoning) if reasoning else None,
        enabled_connectors=EnabledConnectors.model_validate(data["enabled_connectors"]),
        trigger_context=TriggerContext.model_validate(trigger) if trigger else None,
        instructions=data.get("instructions"),
    )


__all__ = ["EuRunState"]
