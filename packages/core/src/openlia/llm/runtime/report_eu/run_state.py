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

from dataclasses import dataclass, field
from typing import Any

from ...capabilities import capabilities_for
from ...types import LLMRequest, LLMResponse, Message
from .events import NullEmitter
from .ledger import CitationLedger
from .prompts import build_system_prompt
from .runner import (
    _connector_prompt_info,
    _dispatch_one,
    _finish,
    _initial_user_turn,
)
from .schemas import RunRequest, RunResult
from .session import _REASONING_OVERHEAD
from .tools import build_catalog
from .tools.web_search import format_web_citation_notice, ingest_web_citations
from .transports import EuDataTransports
from .workspace import RunWorkspace

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


__all__ = ["EuRunState"]
