"""Test fakes for the report_dash_mr engine.

``FakeLLMProvider`` replays a scripted sequence of ``LLMResponse``
objects, one per ``generate`` call, so the runner's tool-use loop can
be exercised deterministically without any network or SDK
dependency.

``script_tool_call`` and ``script_text`` are tiny helpers that
construct the canned responses without verbose ``LLMResponse(...)``
boilerplate at the call sites.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from openlia.llm.base import LLMProvider
from openlia.llm.types import (
    Capabilities,
    Citation,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
    ToolCall,
)


@dataclass
class FakeLLMProvider(LLMProvider):
    """Replay a pre-scripted list of ``LLMResponse``s on successive calls.

    Use ``script_tool_call`` / ``script_text`` to build the script.
    Raises ``StopIteration`` (wrapped as RuntimeError) when the runner
    asks for more turns than scripted — surfaces test bugs loudly.
    """

    scripted_responses: list[LLMResponse] = field(default_factory=list)
    captured_requests: list[LLMRequest] = field(default_factory=list)
    _cursor: int = 0

    def __init__(
        self,
        *,
        scripted_responses: list[LLMResponse] | None = None,
        credentials: ProviderCredentials | None = None,
        model: str = "fake-model",
        capabilities: Capabilities | None = None,
        per_call_delay_seconds: float = 0.0,
    ) -> None:
        super().__init__(
            credentials=credentials
            or ProviderCredentials(api_key="fake", base_url=None, env_var_name=None),
            model=model,
            capabilities=capabilities or Capabilities(web_search_native=True),
        )
        self.scripted_responses = list(scripted_responses or [])
        self.captured_requests = []
        self._cursor = 0
        # Awaited before returning each canned response. Tests that
        # need to race the runner (cancel mid-loop, deadline expiry)
        # set this so each turn yields real time on the event loop.
        self.per_call_delay_seconds = per_call_delay_seconds

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.model, display_name=self.model)]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        import asyncio as _asyncio

        if self.per_call_delay_seconds:
            await _asyncio.sleep(self.per_call_delay_seconds)
        self.captured_requests.append(request)
        if self._cursor >= len(self.scripted_responses):
            raise RuntimeError(
                f"FakeLLMProvider script exhausted after {self._cursor} turns; "
                f"the runner asked for another. Extend the script."
            )
        response = self.scripted_responses[self._cursor]
        self._cursor += 1
        return response

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        # report_dash_mr engine does not stream; satisfy the ABC.
        raise NotImplementedError("FakeLLMProvider.stream is not used by report_dash_mr.")

    async def test_connection(self, model: str) -> TestResult:
        return TestResult(ok=True, latency_ms=0, error_class=None, error_msg=None)


def script_tool_call(
    *,
    name: str,
    arguments: dict,
    call_id: str | None = None,
    text: str = "",
    citations: tuple[Citation, ...] = (),
) -> LLMResponse:
    """Build a response that contains exactly one tool call."""
    call = ToolCall(id=call_id or f"call_{name}", name=name, arguments=arguments)
    return LLMResponse(
        text=text,
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[call],
        citations=citations,
    )


def script_tool_calls(
    *calls: tuple[str, dict],
    text: str = "",
) -> LLMResponse:
    """Build a response with multiple tool calls in one turn."""
    tool_calls = [
        ToolCall(id=f"call_{i}_{name}", name=name, arguments=args)
        for i, (name, args) in enumerate(calls)
    ]
    return LLMResponse(
        text=text,
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=tool_calls,
    )


def script_text(text: str) -> LLMResponse:
    """Build a text-only response (no tool calls)."""
    return LLMResponse(
        text=text,
        finish_reason="stop",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[],
    )
