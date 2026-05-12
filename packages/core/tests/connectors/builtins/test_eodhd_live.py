"""Live EODHD per-tool round-trip tests.

Hits the real EODHD API. Skipped by default because they need an API
key and burn rate-limit. Opt in with `pytest -m live_api`.

For every public method on `ExtendedAPIClient` (i.e. every tool the
chat LLM can call), assert two things:

1. The dispatcher's `dispatch_tool_use` returns a result without raising
   (proves the call signature, kwarg filtering, and any pre-dispatch
   validation are all wired correctly for that tool).
2. The result round-trips through `to_jsonable` -> `json.dumps` without
   `TypeError` (proves no future SDK return-type change will brick the
   chat turn the way Firecrawl's `SearchData` did).

Argument fixtures cover the common case for each tool. Rare edge tools
(insider trades, intraday tick data) get the smallest viable arg set.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from openlia.connectors.builtins.eodhd import EODHD_TEMPLATE
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.serialization import to_jsonable
from openlia.connectors.transports.python_lib import PythonLibTransport
from openlia.connectors.types import (
    Category,
    ConnectorStatus,
    InstanceFactory,
    ToolDefinition,
)

pytestmark = [
    pytest.mark.live_api,
    pytest.mark.asyncio,
    pytest.mark.skipif(not os.environ.get("EODHD_API_KEY"), reason="EODHD_API_KEY not set"),
]


_TODAY = datetime.now(UTC).date()
_LAST_WEEK = (_TODAY - timedelta(days=7)).isoformat()
_TODAY_ISO = _TODAY.isoformat()
_LAST_MONTH = (_TODAY - timedelta(days=30)).isoformat()
_NEXT_MONTH = (_TODAY + timedelta(days=30)).isoformat()


# Per-tool kwargs. Tools omitted from this map use {} (no-arg call).
# Pick small / cheap query shapes — we want correctness, not load tests.
_TOOL_ARGS: dict[str, dict[str, Any]] = {
    "core_inflation_rate": {"country": "US"},
    "cpi_yoy": {"country": "US"},
    "debt_to_gdp": {"country": "US"},
    "gdp_growth_yoy": {"country": "US"},
    "ism_manufacturing_pmi": {"country": "US"},
    "financial_news": {"s": "AAPL.US", "limit": 5},
    "get_bonds_fundamentals_data": {"isin": "US912828YV66"},
    "get_details_trading_hours_stock_market_holidays": {"code": "US"},
    "get_earning_trends_data": {"symbols": "AAPL.US"},
    "get_economic_events_data": {
        "country": "US",
        "date_from": _LAST_WEEK,
        "date_to": _TODAY_ISO,
        "limit": 5,
    },
    "get_eod_historical_stock_market_data": {
        "symbol": "AAPL.US",
        "from_date": _LAST_MONTH,
        "to_date": _TODAY_ISO,
    },
    "get_eod_splits_dividends_data": {"country": "US"},
    "get_exchange_symbols": {"uri": "US"},
    "get_fundamentals_data": {"ticker": "AAPL.US"},
    "get_historical_data": {"symbol": "AAPL.US", "interval": "d", "results": 10},
    "get_historical_dividends_data": {"ticker": "AAPL.US"},
    "get_historical_market_capitalization_data": {
        "ticker": "AAPL.US",
        "from_date": _LAST_MONTH,
        "to_date": _TODAY_ISO,
    },
    "get_historical_splits_data": {"ticker": "AAPL.US"},
    "get_insider_transactions_data": {
        "code": "AAPL.US",
        "date_from": _LAST_MONTH,
        "date_to": _TODAY_ISO,
        "limit": 5,
    },
    "get_intraday_historical_data": {"symbol": "AAPL.US", "interval": "5m"},
    "get_list_of_tickers": {"code": "US"},
    "get_live_stock_prices": {"ticker": "AAPL.US"},
    "get_macro_indicators_data": {"country": "US"},
    "get_options_data": {"ticker": "AAPL.US"},
    "get_sentiment": {"s": "AAPL.US"},
    "get_stock_market_tick_data": {
        "symbol": "AAPL.US",
        # EODHD wants seconds-since-epoch ints for tick endpoints.
        "from_timestamp": int((datetime.now(UTC) - timedelta(hours=2)).timestamp()),
        "to_timestamp": int(datetime.now(UTC).timestamp()),
        "limit": 10,
    },
    "get_technical_indicator_data": {
        "ticker": "AAPL.US",
        "function": "sma",
        "period": 50,
    },
    "get_upcoming_IPOs_data": {
        "from_date": _TODAY_ISO,
        "to_date": _NEXT_MONTH,
    },
    "get_upcoming_earnings_data": {
        "from_date": _TODAY_ISO,
        "to_date": _NEXT_MONTH,
    },
    "get_upcoming_splits_data": {
        "from_date": _TODAY_ISO,
        "to_date": _NEXT_MONTH,
    },
    "stock_market_screener": {"limit": 5},
    "symbol_change_history": {
        "from_date": _LAST_MONTH,
        "to_date": _TODAY_ISO,
    },
    # No-arg tools: get_exchanges, get_list_of_exchanges -> {}
}


async def _build_live_dispatcher() -> tuple[Dispatcher, list[str]]:
    """Build a dispatcher with the live EODHD connector wired up.

    Returns the dispatcher and the list of tool names discovered via
    `list_tools`. Tools are populated on the PreparedConnector so the
    dispatcher's `candidate_tools()` and constraint check both work.
    """
    instance_factory = InstanceFactory(cls="ExtendedAPIClient", args={"api_key": "$EODHD_API_KEY"})
    transport = PythonLibTransport(
        module="openlia.data.eodhd_extended",
        instance_factory=instance_factory,
        secrets={"EODHD_API_KEY": os.environ["EODHD_API_KEY"]},
    )
    discovered = await transport.list_tools()
    tool_names: list[str] = [t["name"] for t in discovered]
    tools = {
        t["name"]: ToolDefinition(
            name=t["name"],
            description=t.get("description", ""),
            input_schema=t.get("input_schema") or {},
        )
        for t in discovered
    }
    prep = PreparedConnector(
        connector_id="live-eodhd",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=transport,
        tools=tools,
    )
    constraints = {"eodhd": tuple(EODHD_TEMPLATE.tool_argument_constraints)}
    dispatcher = Dispatcher(
        connectors={prep.connector_id: prep},
        tool_argument_constraints=constraints,
    )
    return dispatcher, tool_names


async def _enumerate_eodhd_tool_names() -> list[str]:
    transport = PythonLibTransport(
        module="openlia.data.eodhd_extended",
        instance_factory=InstanceFactory(
            cls="ExtendedAPIClient", args={"api_key": "$EODHD_API_KEY"}
        ),
        secrets={"EODHD_API_KEY": os.environ["EODHD_API_KEY"]},
    )
    return [t["name"] for t in await transport.list_tools()]


def _eodhd_tool_names_for_param() -> list[str]:
    """Sync helper for pytest.mark.parametrize. Returns [] if EODHD_API_KEY
    is not set so collection works on machines without the key."""
    if not os.environ.get("EODHD_API_KEY"):
        return []
    import asyncio

    return asyncio.run(_enumerate_eodhd_tool_names())


# Tools we know don't behave well as a generic round-trip:
# - get_intraday_historical_data: requires from/to in unix epoch and
#   often returns 422 on free plans; covered with explicit args above
#   but skip if the SDK rejects the response.
# - get_stock_market_tick_data: paid endpoint, often 403 on free plans.
_PAID_OR_FLAKY_TOOLS = {
    "get_stock_market_tick_data",
    "get_intraday_historical_data",
    "get_options_data",
    "get_bonds_fundamentals_data",
}


@pytest.mark.parametrize("tool_name", _eodhd_tool_names_for_param())
async def test_eodhd_tool_round_trip_returns_json_serializable_result(
    tool_name: str,
) -> None:
    dispatcher, _ = await _build_live_dispatcher()
    args = _TOOL_ARGS.get(tool_name, {})
    prefixed = f"eodhd__{tool_name}"

    if tool_name in _PAID_OR_FLAKY_TOOLS:
        pytest.skip(f"{tool_name}: paid / plan-gated endpoint — exclude from default live run")

    try:
        raw = await dispatcher.dispatch_tool_use(prefixed, args)
    except Exception as exc:
        # Unauthorized / quota / not-on-this-plan responses commonly bubble
        # up as 401/403/422. We only fail the test for unexpected client
        # errors (TypeError, AttributeError, etc).
        msg = str(exc).lower()
        if any(token in msg for token in ("401", "403", "402", "422", "not authorized")):
            pytest.skip(f"{tool_name}: upstream auth/plan rejection ({exc!s})")
        raise

    # The whole point: the result must be JSON-encodable through the
    # dispatch boundary's coercion helper. This catches future SDK
    # changes that introduce non-JSON-native return types.
    coerced = to_jsonable(raw)
    json.dumps(coerced)


async def test_eodhd_financial_news_no_args_short_circuits_via_constraint() -> None:
    """Cross-check Phase 2 against the live API: with no `s` and no `t`,
    the constraint must fire BEFORE the SDK is hit so we don't burn a
    rate-limit slot for a known-bad call."""
    from openlia.connectors.dispatch import MissingRequiredArgumentError

    dispatcher, _ = await _build_live_dispatcher()
    with pytest.raises(MissingRequiredArgumentError) as exc_info:
        await dispatcher.dispatch_tool_use("eodhd__financial_news", {})
    assert exc_info.value.missing == ("s", "t")


async def test_eodhd_financial_news_with_ticker_returns_results() -> None:
    """Sanity: the override + constraint don't break the happy path."""
    dispatcher, _ = await _build_live_dispatcher()
    raw = await dispatcher.dispatch_tool_use("eodhd__financial_news", {"s": "AAPL.US", "limit": 3})
    coerced = to_jsonable(raw)
    json.dumps(coerced)
    # Should be a list of news items.
    assert isinstance(coerced, list)
