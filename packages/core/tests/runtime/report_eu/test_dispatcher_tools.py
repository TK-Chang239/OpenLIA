"""Tests for the dispatcher-backed connector tool wrapper (EU v2)."""

from __future__ import annotations

from typing import Any

import pytest
from openlia.llm.runtime.report_eu.ledger import CitationLedger
from openlia.llm.runtime.report_eu.tools.dispatcher_tools import build_dispatcher_tools
from openlia.llm.runtime.report_v2_3.research import ToolExecutionError, ToolResult
from openlia.llm.runtime.report_v2_3.schemas import DataProviderSource


class FakeDispatcher:
    def __init__(self, tools: list[dict[str, Any]], results: dict[str, Any]) -> None:
        self._tools = tools
        self._results = results

    def candidate_tools(self) -> list[dict[str, Any]]:
        return self._tools

    async def dispatch_tool_use(self, name: str, args: dict[str, Any]) -> Any:
        if name == "boom__fail":
            raise RuntimeError("nope")
        return self._results[name]


def _tool(name: str, category: str = "news") -> dict[str, Any]:
    return {
        "name": name,
        "description": "d",
        "input_schema": {"type": "object", "properties": {}},
        "category": category,
    }


async def test_wraps_candidate_into_ledger_aware_tool() -> None:
    ledger = CitationLedger()
    dispatcher = FakeDispatcher(
        tools=[_tool("newsapi_ai__search")],
        results={"newsapi_ai__search": {"a": 1, "empty": None}},
    )

    tools = build_dispatcher_tools(
        ledger=ledger,
        dispatcher=dispatcher,
        enabled_provider_ids=frozenset({"newsapi_ai"}),
    )

    assert len(tools) == 1
    tool = tools[0]
    assert tool.name == "newsapi_ai__search"

    result = await tool.execute({"q": "x"})

    assert isinstance(result, ToolResult)
    assert result.payload["data"] == {"a": 1}  # None pruned
    source_id = result.payload["source_id"]
    assert ledger.lookup(source_id) is not None
    assert isinstance(result.provenance, DataProviderSource)
    assert result.provenance.provider == "NEWSAPI_AI"
    assert result.provenance.endpoint == "search"


async def test_eodhd_candidate_always_skipped() -> None:
    ledger = CitationLedger()
    dispatcher = FakeDispatcher(
        tools=[_tool("eodhd__get_fundamentals")],
        results={"eodhd__get_fundamentals": {"x": 1}},
    )

    tools = build_dispatcher_tools(
        ledger=ledger,
        dispatcher=dispatcher,
        enabled_provider_ids=frozenset({"eodhd"}),
    )

    assert tools == []


async def test_disabled_provider_skipped() -> None:
    ledger = CitationLedger()
    dispatcher = FakeDispatcher(
        tools=[_tool("newsapi_ai__search")],
        results={"newsapi_ai__search": {"a": 1}},
    )

    tools = build_dispatcher_tools(
        ledger=ledger,
        dispatcher=dispatcher,
        enabled_provider_ids=frozenset({"firecrawl"}),
    )

    assert tools == []


async def test_dispatch_failure_surfaces_tool_execution_error() -> None:
    ledger = CitationLedger()
    dispatcher = FakeDispatcher(
        tools=[_tool("boom__fail")],
        results={},
    )

    tools = build_dispatcher_tools(
        ledger=ledger,
        dispatcher=dispatcher,
        enabled_provider_ids=frozenset({"boom"}),
    )

    assert len(tools) == 1
    with pytest.raises(ToolExecutionError):
        await tools[0].execute({})
