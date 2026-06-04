"""Test fakes for the report_dash_rs engine.

Thin re-export of the FakeLLMProvider / script_tool_calls helpers that
live in the MR engine's test suite.  RS shares the same fake-session
harness because the runner loop is a near-verbatim copy of MR's.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from openlia.llm.base import LLMProvider
from openlia.llm.types import (
    Capabilities,
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
    """Replay a pre-scripted list of ``LLMResponse``s on successive calls."""

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

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.model, display_name=self.model)]

    async def generate(self, request: LLMRequest) -> LLMResponse:
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
        raise NotImplementedError("FakeLLMProvider.stream is not used by report_dash_rs.")

    async def test_connection(self, model: str) -> TestResult:
        return TestResult(ok=True, latency_ms=0, error_class=None, error_msg=None)


def script_tool_calls(
    *calls: tuple[str, dict],
    text: str = "",
) -> LLMResponse:
    """Build a response with one or more tool calls in one turn."""
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
