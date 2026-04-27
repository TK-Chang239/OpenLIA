"""Runtime dispatch: prefix names and route tool_use back to the connector."""

from __future__ import annotations

import pytest
from openlia.connectors.dispatch import (
    Dispatcher,
    DispatchError,
    PreparedConnector,
)
from openlia.connectors.types import Category, ToolDefinition


def _td(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=f"desc-{name}", input_schema={"type": "object"})


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        return {"name": name, "args": arguments}


def test_tools_for_department_prefixes_names():
    eod_t = _FakeTransport()
    fmp_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector(
                connector_id="c1",
                provider_id="eodhd",
                transport=eod_t,
                tools={
                    "get_quote": _td("get_quote"),
                    "get_fundamentals_data": _td("get_fundamentals_data"),
                },
            ),
            "c2": PreparedConnector(
                connector_id="c2",
                provider_id="fmp",
                transport=fmp_t,
                tools={"quote": _td("quote")},
            ),
        },
        allowlist={
            "equity_research": [
                ("c1", "get_quote"),
                ("c1", "get_fundamentals_data"),
                ("c2", "quote"),
            ],
        },
    )

    out = d.tools_for_department("equity_research")
    names = {t["name"] for t in out}
    assert names == {"eodhd__get_quote", "eodhd__get_fundamentals_data", "fmp__quote"}
    assert all(t["input_schema"]["type"] == "object" for t in out)


def test_tools_for_department_skips_missing_connector():
    eod_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector("c1", "eodhd", eod_t, {"get_quote": _td("get_quote")}),
        },
        allowlist={
            "equity_research": [("c1", "get_quote"), ("ghost", "missing")],
        },
    )
    out = d.tools_for_department("equity_research")
    assert [t["name"] for t in out] == ["eodhd__get_quote"]


def test_tools_for_department_skips_uncached_tool():
    eod_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector("c1", "eodhd", eod_t, {"get_quote": _td("get_quote")}),
        },
        allowlist={
            "equity_research": [("c1", "get_quote"), ("c1", "renamed_away")],
        },
    )
    out = d.tools_for_department("equity_research")
    assert [t["name"] for t in out] == ["eodhd__get_quote"]


async def test_dispatch_routes_to_correct_connector():
    eod_t = _FakeTransport()
    fmp_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector("c1", "eodhd", eod_t, {"get_quote": _td("get_quote")}),
            "c2": PreparedConnector("c2", "fmp", fmp_t, {"quote": _td("quote")}),
        },
        allowlist={"equity_research": [("c1", "get_quote"), ("c2", "quote")]},
    )

    await d.dispatch_tool_use("eodhd__get_quote", {"ticker": "AAPL"})
    await d.dispatch_tool_use("fmp__quote", {"ticker": "MSFT"})

    assert eod_t.calls == [("get_quote", {"ticker": "AAPL"})]
    assert fmp_t.calls == [("quote", {"ticker": "MSFT"})]


async def test_dispatch_unknown_provider_raises():
    d = Dispatcher(connectors={}, allowlist={})
    with pytest.raises(DispatchError, match="no connector"):
        await d.dispatch_tool_use("bogus__tool", {})


async def test_dispatch_missing_separator_raises():
    d = Dispatcher(connectors={}, allowlist={})
    with pytest.raises(DispatchError, match="prefix"):
        await d.dispatch_tool_use("noprefix", {})


def test_tools_for_department_filters_by_category():
    fin_t = _FakeTransport()
    news_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c-fin": PreparedConnector("c-fin", "eodhd", fin_t, {"q": _td("q")}),
            "c-news": PreparedConnector("c-news", "newsapi", news_t, {"s": _td("s")}),
        },
        allowlist={"er": [("c-fin", "q"), ("c-news", "s")]},
        connector_categories={
            "c-fin": Category.FINANCIAL,
            "c-news": Category.NEWS,
        },
    )
    out = d.tools_for_department("er", include_categories={Category.FINANCIAL})
    assert {t["name"] for t in out} == {"eodhd__q"}

    out_all = d.tools_for_department("er")
    assert len(out_all) == 2


async def test_dispatch_unknown_tool_for_known_provider_raises():
    eod_t = _FakeTransport()
    d = Dispatcher(
        connectors={
            "c1": PreparedConnector("c1", "eodhd", eod_t, {"get_quote": _td("get_quote")}),
        },
        allowlist={},
    )
    with pytest.raises(DispatchError, match="no connector"):
        await d.dispatch_tool_use("eodhd__never_existed", {})
