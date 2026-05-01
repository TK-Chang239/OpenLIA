"""Multi-turn tool-use resolver client (Phase A step 3).

The agentic client wraps an `LLMProvider` and exposes the
`LlmClient.generate_json` interface. When given a `connector_root`,
it registers filesystem tools (`list_directory`, `read_file`,
`search_files`) and runs a tool-use loop until the LLM emits a final
JSON response. With `connector_root=None`, it degrades to single-shot
(useful when the user hasn't supplied a grounding URL).

Tests use a `FakeProvider` that returns scripted `LLMResponse`
objects so we can drive both branches without touching real models.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from openlia.llm.base import LLMProvider
from openlia.llm.types import LLMChunk, LLMRequest, LLMResponse, ToolCall
from openlia_server.services.agentic_resolver_client import (
    AgenticResolverClient,
    AgenticResolverError,
)


class FakeProvider(LLMProvider):
    """Returns scripted LLMResponse objects in order."""

    def __init__(self, responses: list[LLMResponse]) -> None:
        self._responses = list(responses)
        self.requests: list[LLMRequest] = []

    async def generate(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("FakeProvider exhausted")
        return self._responses.pop(0)

    async def stream(self, request: LLMRequest) -> AsyncIterator[LLMChunk]:
        raise NotImplementedError
        yield  # pragma: no cover

    async def list_models(self):  # type: ignore[override]
        return []

    async def test_connection(self):  # type: ignore[override]
        raise NotImplementedError


def _final(text: str, *, tool_calls: list[ToolCall] | None = None) -> LLMResponse:
    return LLMResponse(
        text=text,
        finish_reason="stop",
        input_tokens=0,
        output_tokens=0,
        tool_calls=tool_calls or [],
    )


@pytest.mark.asyncio
async def test_returns_parsed_json_when_no_tool_calls(tmp_path: Path) -> None:
    provider = FakeProvider([_final('{"need_id": "debt_gdp", "tool_name": "x"}')])
    client = AgenticResolverClient(provider=provider, connector_root=None)

    result = await client.generate_json(prompt="resolve debt_gdp")

    assert result == {"need_id": "debt_gdp", "tool_name": "x"}


@pytest.mark.asyncio
async def test_raises_when_turn_budget_exceeded(tmp_path: Path) -> None:
    # Every turn returns a tool call -- LLM never converges.
    spinning = LLMResponse(
        text="",
        finish_reason="tool_use",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[
            ToolCall(
                id="call_x",
                name="list_directory",
                arguments={"path": "."},
            ),
        ],
    )
    provider = FakeProvider([spinning] * 5)

    client = AgenticResolverClient(provider=provider, connector_root=tmp_path, max_turns=3)

    with pytest.raises(AgenticResolverError):
        await client.generate_json(prompt="resolve x")
    assert len(provider.requests) == 3


@pytest.mark.asyncio
async def test_tool_error_returned_to_llm_as_payload(tmp_path: Path) -> None:
    # First turn: LLM asks for a path that escapes the sandbox.
    # Second turn: LLM emits final JSON.
    turn1 = LLMResponse(
        text="",
        finish_reason="tool_use",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "../../../etc/passwd"},
            ),
        ],
    )
    turn2 = _final('{"unsatisfiable": true}')
    provider = FakeProvider([turn1, turn2])

    client = AgenticResolverClient(provider=provider, connector_root=tmp_path)

    result = await client.generate_json(prompt="resolve x")

    assert result == {"unsatisfiable": True}
    # Tool error should have been delivered to the LLM as a payload, not raised.
    second = provider.requests[1].messages
    tool_msgs = [m for m in second if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "error" in tool_msgs[0].content


@pytest.mark.asyncio
async def test_dispatches_read_file_then_returns_final_json(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools" / "macro.py").write_text(
        "ALLOWED_INDICATORS = {'debt_percent_gdp', 'gdp_current_usd'}\n"
    )

    # Turn 1: LLM asks to read the tool source.
    # Turn 2: with the file contents in scope, LLM emits final JSON.
    turn1 = LLMResponse(
        text="",
        finish_reason="tool_use",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[
            ToolCall(
                id="call_1",
                name="read_file",
                arguments={"path": "tools/macro.py"},
            ),
        ],
    )
    turn2 = _final('{"constants": {"indicator": "debt_percent_gdp"}}')
    provider = FakeProvider([turn1, turn2])

    client = AgenticResolverClient(provider=provider, connector_root=tmp_path)

    result = await client.generate_json(prompt="resolve debt_gdp")

    assert result == {"constants": {"indicator": "debt_percent_gdp"}}
    # Provider was called twice (one tool-call turn, one final).
    assert len(provider.requests) == 2
    # Second request's conversation must include the tool result.
    second_messages = provider.requests[1].messages
    tool_results = [m for m in second_messages if m.role == "tool"]
    assert len(tool_results) == 1
    assert "debt_percent_gdp" in tool_results[0].content
