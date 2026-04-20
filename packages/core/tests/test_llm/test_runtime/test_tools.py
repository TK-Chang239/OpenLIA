from __future__ import annotations

import pytest
from _fakes import FakeDataDispatcher, FakeSearchAdapter
from openlia.llm.runtime.tools import (
    ToolCallResult,
    ToolDispatcher,
)
from openlia.llm.runtime.web_search import WebSearchResolution, WebSearchResult
from openlia.llm.types import ToolCall

pytestmark = pytest.mark.asyncio

_MANIFEST = {
    "equity_research": {
        "stock_quote": {
            "name": "stock_quote",
            "description": "Real-time stock quote for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
        "financial_statements": {
            "name": "financial_statements",
            "description": "Latest 10-K/10-Q filings.",
            "parameters": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        },
    }
}


async def test_build_returns_mapping_tools_plus_find_more_data() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=False)
    names = [t.name for t in tools]
    assert "stock_quote" in names
    assert "financial_statements" in names
    assert "find_more_data" in names
    assert "web_search" not in names


async def test_build_appends_web_search_when_available() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(
            available=True, variant="configured", adapter=FakeSearchAdapter()
        ),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" in [t.name for t in tools]


async def test_build_omits_web_search_even_if_has_flag_when_unavailable() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(available=False, variant=None, adapter=None),
    )
    tools = await disp.build("equity_research", has_web_search=True)
    assert "web_search" not in [t.name for t in tools]


async def test_dispatch_requirement_tool_returns_ok_result() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"stock_quote": {"symbol": "AAPL", "price": 190.5}},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert isinstance(result, ToolCallResult)
    assert result.ok is True
    assert result.payload == {"symbol": "AAPL", "price": 190.5}
    assert "AAPL" in result.summary


async def test_dispatch_requirement_tool_surfaces_failure_as_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST, raise_for={"stock_quote"})
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
    )
    assert result.ok is False
    assert "Failed" in result.summary


async def test_dispatch_find_more_data_hit_adds_tool_for_next_turn() -> None:
    new_tool = {
        "name": "options_chain",
        "description": "Options chain",
        "parameters": {
            "type": "object",
            "properties": {"symbol": {"type": "string"}},
            "required": ["symbol"],
        },
    }
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={"expand::options chain": new_tool},
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    before = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" not in [t.name for t in before]

    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="find_more_data", arguments={"description": "options chain"}),
    )
    assert result.ok is True
    after = await disp.build("equity_research", has_web_search=False)
    assert "options_chain" in [t.name for t in after]


async def test_dispatch_find_more_data_miss_returns_ok_false() -> None:
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="find_more_data", arguments={"description": "nonsense data"}),
    )
    assert result.ok is False
    assert "not available" in result.summary.lower() or "no match" in result.summary.lower()


async def test_dispatch_web_search_configured_calls_adapter() -> None:
    adapter = FakeSearchAdapter(
        results=[WebSearchResult(title="AAPL news", url="https://u", snippet="...")]
    )
    data = FakeDataDispatcher(manifest=_MANIFEST)
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(True, "configured", adapter),
    )
    result = await disp.dispatch(
        department_id="equity_research",
        call=ToolCall(id="c1", name="web_search", arguments={"query": "AAPL earnings"}),
    )
    assert result.ok is True
    assert result.payload["results"][0]["title"] == "AAPL news"


async def test_dispatch_many_runs_in_parallel() -> None:
    data = FakeDataDispatcher(
        manifest=_MANIFEST,
        results={
            "stock_quote": {"symbol": "AAPL", "price": 1},
            "financial_statements": {"symbol": "AAPL", "filings": []},
        },
    )
    disp = ToolDispatcher(
        data_dispatcher=data,
        web_search=WebSearchResolution(False, None, None),
    )
    results = await disp.dispatch_many(
        department_id="equity_research",
        calls=[
            ToolCall(id="c1", name="stock_quote", arguments={"symbol": "AAPL"}),
            ToolCall(id="c2", name="financial_statements", arguments={"symbol": "AAPL"}),
        ],
    )
    assert len(results) == 2
    assert all(r.ok for r in results)
    assert [r.call_id for r in results] == ["c1", "c2"]


async def test_response_normalization_caps_arrays() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    big = {"items": list(range(100)), "nullable": None, "ok": True}
    out = _normalize_payload(big, max_array_len=10)
    assert len(out["items"]) == 10
    assert out["truncated"] is True
    assert "nullable" not in out
    assert out["ok"] is True


async def test_response_normalization_leaves_small_arrays_alone() -> None:
    from openlia.llm.runtime.tools import _normalize_payload

    out = _normalize_payload({"items": [1, 2, 3]}, max_array_len=10)
    assert out == {"items": [1, 2, 3]}
