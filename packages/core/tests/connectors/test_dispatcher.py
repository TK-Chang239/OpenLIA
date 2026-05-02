"""Dispatcher tests (v2): candidate pool, fetch_need, in_department."""

from __future__ import annotations

from typing import Any

import pytest
from openlia.connectors.dispatch import (
    Dispatcher,
    DispatchError,
    NeedNotResolved,
    PreparedConnector,
)
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    ConnectorStatus,
    ParamBinding,
    ToolDefinition,
)


def _td(name: str) -> ToolDefinition:
    return ToolDefinition(name=name, description=f"desc-{name}", input_schema={"type": "object"})


def _cd(qualname: str) -> CallableDefinition:
    return CallableDefinition(qualname=qualname, signature="(...)->Any", doc="")


class _FakeTransport:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        return {"name": name, "args": arguments}


def _eodhd_mcp() -> PreparedConnector:
    return PreparedConnector(
        connector_id="c1",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),
        tools={"get_quote": _td("get_quote")},
    )


def _fmp_mcp() -> PreparedConnector:
    return PreparedConnector(
        connector_id="c2",
        provider_id="fmp",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),
        tools={"quote": _td("quote")},
    )


def _pending_conn() -> PreparedConnector:
    return PreparedConnector(
        connector_id="c3",
        provider_id="newsapi",
        category=Category.NEWS,
        status=ConnectorStatus.PENDING,
        transport=_FakeTransport(),
        tools={"search": _td("search")},
    )


# ----- candidate_tools -----


def test_candidate_tools_includes_only_validated_connectors():
    d = Dispatcher(
        connectors={
            "c1": _eodhd_mcp(),
            "c2": _fmp_mcp(),
            "c3": _pending_conn(),
        }
    )
    out = d.candidate_tools()
    names = {t["name"] for t in out}
    assert names == {"eodhd__get_quote", "fmp__quote"}
    assert all(t["input_schema"] == {"type": "object"} for t in out)


def test_candidate_tools_empty_when_no_validated_connectors():
    d = Dispatcher(connectors={"c3": _pending_conn()})
    assert d.candidate_tools() == []


# ----- dispatch_tool_use -----


async def test_dispatch_routes_to_correct_connector_by_prefix():
    eod = _eodhd_mcp()
    fmp = _fmp_mcp()
    d = Dispatcher(connectors={"c1": eod, "c2": fmp})

    await d.dispatch_tool_use("eodhd__get_quote", {"ticker": "AAPL"})
    await d.dispatch_tool_use("fmp__quote", {"ticker": "MSFT"})

    assert eod.transport.calls == [("get_quote", {"ticker": "AAPL"})]  # type: ignore[attr-defined]
    assert fmp.transport.calls == [("quote", {"ticker": "MSFT"})]  # type: ignore[attr-defined]


async def test_dispatch_unknown_provider_raises():
    d = Dispatcher(connectors={})
    with pytest.raises(DispatchError, match="no connector"):
        await d.dispatch_tool_use("bogus__tool", {})


async def test_dispatch_missing_separator_raises():
    d = Dispatcher(connectors={})
    with pytest.raises(DispatchError, match="prefix"):
        await d.dispatch_tool_use("noprefix", {})


# ----- in_department / fetch_need -----


async def test_fetch_need_without_department_context_raises():
    d = Dispatcher(connectors={})
    with pytest.raises(DispatchError, match="in_department"):
        await d.fetch_need("debt_gdp", country="US")


async def test_fetch_need_with_no_resolved_spec_raises_need_not_resolved():
    d = Dispatcher(connectors={"c1": _eodhd_mcp()}, callable_specs={})
    async with d.in_department("macro_research"):
        with pytest.raises(NeedNotResolved):
            await d.fetch_need("debt_gdp", country="US")


async def test_fetch_need_mcp_spec_happy_path_with_transform_and_constants():
    eod = _eodhd_mcp()
    eod.tools["get_economic_indicator"] = _td("get_economic_indicator")
    spec = CallableSpec(
        need_id="debt_gdp",
        access_mode="cli_mcp",
        tool_name="get_economic_indicator",
        param_bindings={"country": ParamBinding(to_arg="country", transform="upper")},
        constants={"indicator": "DEBT_GDP_PCT"},
        shape="float",
    )
    d = Dispatcher(
        connectors={"c1": eod},
        callable_specs={("macro_research", "debt_gdp"): spec},
    )
    async with d.in_department("macro_research"):
        result = await d.fetch_need("debt_gdp", country="us")

    assert eod.transport.calls == [  # type: ignore[attr-defined]
        ("get_economic_indicator", {"country": "US", "indicator": "DEBT_GDP_PCT"}),
    ]
    assert result == {
        "name": "get_economic_indicator",
        "args": {"country": "US", "indicator": "DEBT_GDP_PCT"},
    }


async def test_fetch_need_python_lib_spec_happy_path():
    transport = _FakeTransport()
    conn = PreparedConnector(
        connector_id="c1",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=transport,
        tools={},
        callables={"economic_data": _cd("APIClient.economic_data")},
    )
    spec = CallableSpec(
        need_id="debt_gdp",
        access_mode="python_lib",
        module="eodhd",
        method="economic_data",
        param_bindings={"country": ParamBinding(to_arg="country_code", transform=None)},
        constants={"indicator": "DEBT_GDP_PCT"},
        shape="float",
    )
    d = Dispatcher(
        connectors={"c1": conn},
        callable_specs={("macro_research", "debt_gdp"): spec},
    )
    async with d.in_department("macro_research"):
        await d.fetch_need("debt_gdp", country="US")

    assert transport.calls == [
        ("economic_data", {"country_code": "US", "indicator": "DEBT_GDP_PCT"}),
    ]


async def test_fetch_need_unknown_transform_raises():
    eod = _eodhd_mcp()
    eod.tools["get_thing"] = _td("get_thing")
    spec = CallableSpec(
        need_id="x",
        access_mode="cli_mcp",
        tool_name="get_thing",
        param_bindings={"v": ParamBinding(to_arg="v", transform="bogus_transform")},
    )
    d = Dispatcher(
        connectors={"c1": eod},
        callable_specs={("dept", "x"): spec},
    )
    async with d.in_department("dept"):
        with pytest.raises(DispatchError, match="unknown transform"):
            await d.fetch_need("x", v="hi")


# ----- callable_specs_for -----


def test_callable_specs_for_filters_by_department():
    spec_a = CallableSpec(need_id="a", access_mode="cli_mcp", tool_name="t")
    spec_b = CallableSpec(need_id="b", access_mode="cli_mcp", tool_name="t")
    spec_c = CallableSpec(need_id="c", access_mode="cli_mcp", tool_name="t")
    d = Dispatcher(
        connectors={},
        callable_specs={
            ("macro_research", "a"): spec_a,
            ("macro_research", "b"): spec_b,
            ("retail_sentiment", "c"): spec_c,
        },
    )
    out = d.callable_specs_for("macro_research")
    assert {s.need_id for s in out} == {"a", "b"}


# ----- result_path -----


@pytest.mark.asyncio
async def test_invoke_spec_walks_result_path() -> None:
    """When result_path is set, dispatcher reduces tool result to the nested value."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"data": {"usd_share_pct": 58.4, "as_of": "2026-Q1"}}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={
            "firecrawl_extract": ToolDefinition(
                name="firecrawl_extract", description="", input_schema={}
            )
        },
    )
    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        constants={"urls": ["https://example"]},
        result_path=("data", "usd_share_pct"),
        shape="float",
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == 58.4


@pytest.mark.asyncio
async def test_invoke_spec_empty_result_path_returns_raw() -> None:
    """When result_path is empty, dispatcher returns the tool result unchanged."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"value": 42}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="p",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={"t": ToolDefinition(name="t", description="", input_schema={})},
    )
    spec = CallableSpec(need_id="n", access_mode="remote_mcp", tool_name="t")
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == {"value": 42}


@pytest.mark.asyncio
async def test_invoke_spec_result_path_missing_key_raises() -> None:
    """If a key in result_path is absent from the tool result, dispatcher raises DispatchError."""

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return {"data": {}}  # missing usd_share_pct

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        tools={
            "firecrawl_extract": ToolDefinition(
                name="firecrawl_extract", description="", input_schema={}
            )
        },
    )
    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="remote_mcp",
        tool_name="firecrawl_extract",
        result_path=("data", "usd_share_pct"),
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    with pytest.raises(DispatchError, match="result_path"):
        await dispatcher._invoke_spec(conn, spec, runtime_args={})


@pytest.mark.asyncio
async def test_invoke_spec_walks_result_path_via_attributes() -> None:
    """result_path falls back to attribute access for non-dict results.

    Pydantic models / dataclasses returned by python_lib transports (e.g.
    Firecrawl SDK's Document) need attribute traversal, not dict subscript.
    """
    from dataclasses import dataclass

    @dataclass
    class _Doc:
        json: dict[str, float]

    class _FakeTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return _Doc(json={"usd_share_pct": 58.4})

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(),  # type: ignore[arg-type]
        callables={
            "Firecrawl.scrape": CallableDefinition(
                qualname="Firecrawl.scrape", signature="(url: str) -> Any", doc=""
            )
        },
    )
    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="python_lib",
        method="Firecrawl.scrape",
        result_path=("json", "usd_share_pct"),
        shape="float",
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == 58.4
