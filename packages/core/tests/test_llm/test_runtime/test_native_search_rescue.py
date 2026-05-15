"""Phase 0 contract: I-a rescue path.

When a provider's native web_search fails mid-turn and a configured
search adapter is available, the runtime rewrites the failure into a
synthetic `web_search` ToolCall that the standard dispatch loop fires
on the next turn. Single rewrite per (turn_idx, query) — guardrail G-1
prevents retry loops. When no configured adapter is available, the
failure stays inline; the two-source-discipline prompt directs the
model to write "Data not available."
"""

from __future__ import annotations

from openlia.llm.runtime.report import _rescue_failed_searches
from openlia.llm.runtime.web_search import WebSearchResolution
from openlia.llm.types import FailedSearch, LLMResponse


class _StubSearchAdapter:
    async def search(self, query: str):
        return []


def _response_with_failure(query: str = "AAPL recent news", turn_idx: int = 0) -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="end_turn",
        input_tokens=10,
        output_tokens=10,
        tool_calls=[],
        server_tool_failures=(
            FailedSearch(
                query=query,
                error_kind="rate_limit",
                error_message="429 too many requests",
                turn_idx=turn_idx,
            ),
        ),
    )


def test_rescue_rewrites_failure_into_web_search_tool_call() -> None:
    """When a configured adapter is available, each unique failed query
    becomes a synthetic web_search ToolCall the dispatch loop will fire
    on the next turn."""
    response = _response_with_failure(query="AAPL recent news", turn_idx=0)
    seen: set[tuple[int, str]] = set()

    rescued = _rescue_failed_searches(
        response,
        web_search_resolution=WebSearchResolution(
            available=True, variant="configured", adapter=_StubSearchAdapter()
        ),
        seen=seen,
        trace=lambda *_args, **_kw: None,
    )

    rescue_calls = [c for c in rescued.tool_calls if c.name == "web_search"]
    assert len(rescue_calls) == 1
    assert rescue_calls[0].arguments == {"query": "AAPL recent news"}
    assert (0, "AAPL recent news") in seen


def test_rescue_skips_when_no_configured_adapter() -> None:
    """No fallback when variant is native (no configured adapter to
    route to). Failure stays inline; prompt handles via 'Data not
    available'. tool_calls untouched."""
    response = _response_with_failure()
    seen: set[tuple[int, str]] = set()

    rescued = _rescue_failed_searches(
        response,
        web_search_resolution=WebSearchResolution(
            available=True, variant="native", adapter=None
        ),
        seen=seen,
        trace=lambda *_args, **_kw: None,
    )

    assert rescued.tool_calls == response.tool_calls
    assert seen == set()


def test_rescue_does_not_double_rewrite_same_query_g1() -> None:
    """Guardrail G-1: a (turn_idx, query) pair already in the seen set
    is not rewritten again. Prevents an infinite native-fail then
    configured-fail then re-rewrite loop."""
    response = _response_with_failure(query="repeat", turn_idx=2)
    seen: set[tuple[int, str]] = {(2, "repeat")}

    rescued = _rescue_failed_searches(
        response,
        web_search_resolution=WebSearchResolution(
            available=True, variant="configured", adapter=_StubSearchAdapter()
        ),
        seen=seen,
        trace=lambda *_args, **_kw: None,
    )

    assert [c for c in rescued.tool_calls if c.name == "web_search"] == []


def test_writing_phase_tools_exclude_web_search() -> None:
    """Guardrail G-5: the writing phase composes its tool list inline
    from `_submit_report_tool()` + `_READ_PAYLOAD_SCHEMA` only — never
    `web_search`. A search call mid-write triggers cost spikes, turn
    blowout, and bypasses the validation pipeline. Pin the existing
    correct behavior so a future tool addition can't regress it
    silently."""
    from openlia.llm.runtime.report import _READ_PAYLOAD_SCHEMA, _submit_report_tool

    writing_tools = [_submit_report_tool(), _READ_PAYLOAD_SCHEMA]
    names = [t.name for t in writing_tools]
    assert "web_search" not in names
    assert "submit_report" in names
    assert "read_payload" in names


def test_rescue_passes_through_when_no_failures() -> None:
    """Response without server_tool_failures is returned unchanged."""
    response = LLMResponse(
        text="hello",
        finish_reason="end_turn",
        input_tokens=1,
        output_tokens=1,
        tool_calls=[],
    )
    seen: set[tuple[int, str]] = set()

    rescued = _rescue_failed_searches(
        response,
        web_search_resolution=WebSearchResolution(
            available=True, variant="configured", adapter=_StubSearchAdapter()
        ),
        seen=seen,
        trace=lambda *_args, **_kw: None,
    )

    assert rescued is response
    assert seen == set()
