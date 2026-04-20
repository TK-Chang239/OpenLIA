"""Shared fakes for runtime tests: FakeProvider, FakeDataDispatcher, FakeSearchAdapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from openlia.llm.base import LLMProvider
from openlia.llm.runtime.web_search import WebSearchResult
from openlia.llm.types import (
    Capabilities,
    LLMChunk,
    LLMRequest,
    LLMResponse,
    ModelInfo,
    ProviderCredentials,
    TestResult,
)


@dataclass
class FakeProviderScript:
    """Declarative description of what FakeProvider should yield.

    Entries correspond to one provider turn each. Each entry is either:
      - ("text", "...") — yield a single LLMChunk with that text
      - ("tokens", ["Apple", " sold"]) — yield one LLMChunk per token
      - ("tool_calls", [ToolCall(...), ...]) — yield a synthetic tool-calling
         LLMResponse (via generate) as the final result of this turn
      - ("final", "text", {"finish_reason": "stop", ...}) — emit final text
         and stop the stream.
    """

    turns: list[tuple[str, Any]] = field(default_factory=list)


class FakeProvider(LLMProvider):
    kind = "fake"

    def __init__(
        self,
        *,
        credentials: ProviderCredentials | None = None,
        model: str = "fake-1",
        capabilities: Capabilities | None = None,
        script: FakeProviderScript | None = None,
    ) -> None:
        super().__init__(
            credentials=credentials or ProviderCredentials(api_key="k", base_url=None),
            model=model,
            capabilities=capabilities
            or Capabilities(
                streaming=True,
                tool_calling=True,
                structured_output=True,
            ),
        )
        self._script = script or FakeProviderScript()
        self._turn_index = 0
        self.captured_requests: list[LLMRequest] = []

    async def list_models(self) -> list[ModelInfo]:
        return [ModelInfo(id=self.model, display_name=self.model, context_window=8192)]

    async def test_connection(self, model: str) -> TestResult:
        return TestResult(ok=True, latency_ms=1, error_class=None, error_msg=None)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.captured_requests.append(request)
        kind, payload = self._script.turns[self._turn_index]
        self._turn_index += 1
        if kind == "tool_calls":
            return LLMResponse(
                text="",
                finish_reason="tool_calls",
                input_tokens=0,
                output_tokens=0,
                tool_calls=list(payload),
            )
        if kind == "final_json":
            return LLMResponse(
                text=payload,
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
                tool_calls=[],
            )
        if kind == "final":
            return LLMResponse(
                text=payload,
                finish_reason="stop",
                input_tokens=0,
                output_tokens=0,
                tool_calls=[],
            )
        raise AssertionError(f"unknown turn kind {kind}")

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        self.captured_requests.append(request)
        kind, payload = self._script.turns[self._turn_index]
        self._turn_index += 1
        if kind == "tokens":
            for t in payload:
                yield LLMChunk(delta=t, finish_reason=None)
            yield LLMChunk(delta="", finish_reason="stop")
            return
        if kind == "tool_calls":
            yield LLMChunk(delta="", finish_reason="tool_calls")
            return
        if kind == "text":
            yield LLMChunk(delta=payload, finish_reason="stop")
            return
        raise AssertionError(f"unknown stream turn {kind}")


@dataclass
class FakeDataDispatcher:
    """Implements the DataProviderDispatcher Protocol used by ToolDispatcher."""

    manifest: dict[str, dict[str, Any]] = field(default_factory=dict)
    results: dict[str, dict[str, Any]] = field(default_factory=dict)
    raise_for: set[str] = field(default_factory=set)

    async def list_requirement_tools(self, department_id: str) -> list[dict[str, Any]]:
        return list(self.manifest.get(department_id, {}).values())

    async def dispatch_requirement(
        self, *, tool_name: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        if tool_name in self.raise_for:
            raise RuntimeError(f"provider blew up for {tool_name}")
        return self.results.get(tool_name, {"tool": tool_name, "args": arguments})

    async def find_more_data(
        self, *, department_id: str, description: str
    ) -> dict[str, Any] | None:
        return self.results.get(f"expand::{description}")


@dataclass
class FakeSearchAdapter:
    results: list[WebSearchResult] = field(default_factory=list)

    async def search(self, query: str) -> list[WebSearchResult]:
        return self.results or [
            WebSearchResult(title=f"Result for {query}", url="https://x", snippet="")
        ]
