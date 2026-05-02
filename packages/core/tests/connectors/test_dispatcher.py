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


# ----- result_reducer -----


@pytest.mark.asyncio
async def test_invoke_spec_applies_latest_value_by_date_reducer() -> None:
    """FMP's economics-indicators tool returns list[{name, date, value}] —
    not a single float. The `latest_value_by_date` reducer picks the most
    recent record by `date` and returns its `value` as a float. Without
    this, runners declared with `shape='float'` would receive the raw
    list and fail downstream.
    """

    class _T:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return [
                {"name": "inflationRate", "date": "2026-03-01", "value": 2.31},
                {"name": "inflationRate", "date": "2026-04-01", "value": 2.55},
                {"name": "inflationRate", "date": "2026-02-01", "value": 2.20},
            ]

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="fmp",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_T(),  # type: ignore[arg-type]
    )
    spec = CallableSpec(
        need_id="cpi_yoy",
        access_mode="remote_mcp",
        tool_name="economics",
        constants={"endpoint": "economics-indicators", "name": "inflationRate"},
        result_reducer="latest_value_by_date",
        shape="float",
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    assert result == 2.55


@pytest.mark.asyncio
async def test_invoke_spec_applies_yoy_pct_quarterly_reducer() -> None:
    """FMP's realGDP indicator returns quarterly *levels*, not YoY %.
    The yoy_pct_quarterly reducer computes
    (latest - 4-quarters-back) / 4-quarters-back * 100 from the series
    so a runner expecting `shape='float'` gets the YoY % directly.
    """

    class _T:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            return [
                {"date": "2026-01-01", "value": 24174.527},
                {"date": "2025-10-01", "value": 24055.749},
                {"date": "2025-07-01", "value": 24026.834},
                {"date": "2025-04-01", "value": 23770.976},
                {"date": "2025-01-01", "value": 23548.21},
                {"date": "2024-10-01", "value": 23300.0},
            ]

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="fmp",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_T(),  # type: ignore[arg-type]
    )
    spec = CallableSpec(
        need_id="gdp_yoy",
        access_mode="remote_mcp",
        tool_name="economics",
        constants={"endpoint": "economics-indicators", "name": "realGDP"},
        result_reducer="yoy_pct_quarterly",
        shape="float",
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    result = await dispatcher._invoke_spec(conn, spec, runtime_args={})
    # latest=24174.527, 4-back=23548.21 → (24174.527-23548.21)/23548.21*100 ≈ 2.66
    assert result == pytest.approx(2.66, abs=0.01)


# ----- runtime arg filtering -----


@pytest.mark.asyncio
async def test_invoke_spec_drops_unbound_runtime_args() -> None:
    """Runtime args that have no matching `param_bindings` entry must be
    dropped, not passed through. parse_mr_requirement adds country=US
    uniformly for every macro_indicator: requirement, but Firecrawl-scrape
    specs don't accept a country kwarg — passing it through becomes
    `Firecrawl.scrape(url=..., formats=..., country='US')` which raises
    TypeError on the SDK signature.
    """
    captured: dict[str, dict] = {}

    class _T:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            captured["args"] = args
            return {"json": {"x": 1.0}}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    conn = PreparedConnector(
        connector_id="c1",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_T(),  # type: ignore[arg-type]
    )
    spec = CallableSpec(
        need_id="interest_revenue",
        access_mode="python_lib",
        method="Firecrawl.scrape",
        constants={"url": "https://x"},
        # No bindings — every kwarg is unbound.
    )
    dispatcher = Dispatcher(connectors={"c1": conn})
    await dispatcher._invoke_spec(conn, spec, runtime_args={"country": "US"})
    assert "country" not in captured["args"]
    assert captured["args"] == {"url": "https://x"}


# ----- spec_connector_id routing -----


@pytest.mark.asyncio
async def test_fetch_need_routes_via_persisted_spec_connector_id() -> None:
    """When a spec's owning connector is recorded by id (set by the
    server's hydrator from RunnerCallableSpec.connector_id), the
    dispatcher routes there directly — no scanning by method qualname.

    Without this, two python_lib connectors with disjoint callable
    surfaces (e.g. EODHD + Firecrawl) cause method names that don't
    appear in either registry to fall back to "any python_lib
    connector", which routes wrong (the call lands on the first
    connector registered, not the one that owns the spec).
    """
    captured: dict[str, str] = {}

    class _FCTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            captured["target"] = "firecrawl"
            return {"json": {"x": 1.0}}

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    class _EODHDTransport:
        async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
            captured["target"] = "eodhd"
            return None  # would normally raise AttributeError on getattr

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def list_callables(self) -> list[CallableDefinition]:
            return []

    eodhd = PreparedConnector(
        connector_id="eodhd-id",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_EODHDTransport(),  # type: ignore[arg-type]
        callables={
            "ExtendedAPIClient.get_live_stock_prices": CallableDefinition(
                qualname="ExtendedAPIClient.get_live_stock_prices",
                signature="()",
                doc="",
            )
        },
    )
    firecrawl = PreparedConnector(
        connector_id="firecrawl-id",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=_FCTransport(),  # type: ignore[arg-type]
        # Firecrawl's instance methods aren't on the class — introspect
        # finds nothing. Empty callables registry.
        callables={},
    )

    spec = CallableSpec(
        need_id="usd_fx_reserve_share",
        access_mode="python_lib",
        method="Firecrawl.scrape",
        result_path=("json", "x"),
        shape="float",
    )

    dispatcher = Dispatcher(
        connectors={"eodhd-id": eodhd, "firecrawl-id": firecrawl},
        callable_specs={("macro_research", "usd_fx_reserve_share"): spec},
        spec_connector_ids={
            ("macro_research", "usd_fx_reserve_share"): "firecrawl-id",
        },
    )

    async with dispatcher.in_department("macro_research"):
        result = await dispatcher.fetch_need("usd_fx_reserve_share")
    assert result == 1.0
    assert captured["target"] == "firecrawl"


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
