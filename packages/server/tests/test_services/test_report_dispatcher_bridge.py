"""Tests for the simplified ReportDispatcherBridge (Phase B shape)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.types import Category, ConnectorStatus
from openlia_server.services.report_dispatcher_bridge import ReportDispatcherBridge


def _make_dispatcher(tools: list[dict[str, Any]], dispatch_result: Any = None) -> MagicMock:
    dispatcher = MagicMock()
    dispatcher.candidate_tools.return_value = tools
    dispatcher.dispatch_tool_use = AsyncMock(return_value=dispatch_result or {"ok": True})
    return dispatcher


@pytest.mark.asyncio
async def test_list_requirement_tools_returns_empty() -> None:
    """Empty starter pack — list_requirement_tools always returns []."""
    dispatcher = _make_dispatcher(
        [{"name": "fmp__quote", "description": "Get quote", "input_schema": {"type": "object"}}]
    )
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.list_requirement_tools("equity_research")
    assert result == []


@pytest.mark.asyncio
async def test_list_requirement_tools_wrong_department_raises() -> None:
    dispatcher = _make_dispatcher([])
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    with pytest.raises(RuntimeError, match="pinned to 'equity_research'"):
        await bridge.list_requirement_tools("morning_briefing")


@pytest.mark.asyncio
async def test_dispatch_requirement_passthrough_dict() -> None:
    """Dict results pass through unchanged."""
    dispatcher = _make_dispatcher([], dispatch_result={"price": 42.0})
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.dispatch_requirement(tool_name="fmp__quote", arguments={"symbol": "AAPL"})
    assert result == {"price": 42.0}
    dispatcher.dispatch_tool_use.assert_awaited_once_with("fmp__quote", {"symbol": "AAPL"})


@pytest.mark.asyncio
async def test_dispatch_requirement_coerces_non_dict() -> None:
    """Non-dict results are wrapped in {'value': ...}."""
    dispatcher = _make_dispatcher([], dispatch_result="raw string")
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.dispatch_requirement(tool_name="fmp__quote", arguments={})
    assert result == {"value": "raw string"}


@pytest.mark.asyncio
async def test_expand_tools_returns_full_inventory() -> None:
    """expand_tools returns all candidate tools from the dispatcher."""
    tools = [
        {"name": "fmp__quote", "description": "Get quote", "input_schema": {"type": "object"}},
        {"name": "eodhd__news", "description": "Get news", "input_schema": {"type": "object"}},
    ]
    dispatcher = _make_dispatcher(tools)
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.expand_tools(department_id="equity_research", reason="need market data")
    assert len(result) == 2
    names = {t["name"] for t in result}
    assert names == {"fmp__quote", "eodhd__news"}
    for entry in result:
        assert "name" in entry
        assert "description" in entry
        assert "parameters" in entry


@pytest.mark.asyncio
async def test_expand_tools_wrong_department_raises() -> None:
    dispatcher = _make_dispatcher([])
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    with pytest.raises(RuntimeError, match="pinned to 'equity_research'"):
        await bridge.expand_tools(department_id="morning_briefing", reason="test")


@pytest.mark.asyncio
async def test_expand_tools_maps_input_schema_to_parameters() -> None:
    """input_schema key from dispatcher is renamed to parameters in output."""
    tools = [
        {
            "name": "fmp__quote",
            "description": "Get quote",
            "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
        }
    ]
    dispatcher = _make_dispatcher(tools)
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.expand_tools(department_id="equity_research", reason="test")
    assert result[0]["parameters"] == {
        "type": "object",
        "properties": {"symbol": {"type": "string"}},
    }


@pytest.mark.asyncio
async def test_expand_tools_missing_input_schema_defaults_to_empty_dict() -> None:
    """Tools missing input_schema get an empty dict for parameters."""
    tools = [{"name": "simple_tool"}]
    dispatcher = _make_dispatcher(tools)
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.expand_tools(department_id="equity_research", reason="test")
    assert result[0]["parameters"] == {}


# ---------------------------------------------------------------------------
# available_categories tests
# ---------------------------------------------------------------------------


def _fake_transport() -> MagicMock:
    t = MagicMock()
    t.call_tool = AsyncMock(return_value={})
    t.list_tools = AsyncMock(return_value=[])
    t.aclose = AsyncMock()
    return t


def _make_real_dispatcher(
    connectors: dict[str, PreparedConnector],
) -> Dispatcher:
    return Dispatcher(connectors=connectors)


@pytest.mark.asyncio
async def test_available_categories() -> None:
    """Returns sorted distinct categories from VALIDATED connectors, web_search excluded."""
    connectors = {
        "fmp": PreparedConnector(
            connector_id="fmp",
            provider_id="fmp",
            category=Category.FINANCIAL,
            status=ConnectorStatus.VALIDATED,
            transport=_fake_transport(),
        ),
        "eodhd_news": PreparedConnector(
            connector_id="eodhd_news",
            provider_id="eodhd",
            category=Category.NEWS,
            status=ConnectorStatus.VALIDATED,
            transport=_fake_transport(),
        ),
        "reddit": PreparedConnector(
            connector_id="reddit",
            provider_id="reddit",
            category=Category.SOCIAL,
            status=ConnectorStatus.VALIDATED,
            transport=_fake_transport(),
        ),
        "brave": PreparedConnector(
            connector_id="brave",
            provider_id="brave",
            category=Category.WEB_SEARCH,
            status=ConnectorStatus.VALIDATED,
            transport=_fake_transport(),
        ),
    }
    dispatcher = _make_real_dispatcher(connectors)
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.available_categories()
    assert result == ["financial", "news", "social"]


@pytest.mark.asyncio
async def test_available_categories_skips_unvalidated() -> None:
    """Connectors with status FAILED are excluded from results."""
    connectors = {
        "fmp": PreparedConnector(
            connector_id="fmp",
            provider_id="fmp",
            category=Category.FINANCIAL,
            status=ConnectorStatus.VALIDATED,
            transport=_fake_transport(),
        ),
        "broken_news": PreparedConnector(
            connector_id="broken_news",
            provider_id="news_co",
            category=Category.NEWS,
            status=ConnectorStatus.FAILED,
            transport=_fake_transport(),
        ),
    }
    dispatcher = _make_real_dispatcher(connectors)
    bridge = ReportDispatcherBridge(dispatcher=dispatcher, department_id="equity_research")
    result = await bridge.available_categories()
    assert result == ["financial"]
