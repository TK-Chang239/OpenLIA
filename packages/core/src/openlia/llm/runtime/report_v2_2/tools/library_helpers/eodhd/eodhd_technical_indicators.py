"""eodhd_technical_indicators — technical indicator time series for a ticker."""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2_2 import (
    Category,
    DirectoryEntry,
    HelperOutput,
    HelperParam,
    HelperSchema,
    MechanicalContract,
    SelectionGuidance,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import register_helper

from . import client

_VALID_FUNCTIONS = frozenset(
    [
        "avgvol",
        "avgvolccy",
        "sma",
        "ema",
        "wma",
        "volatility",
        "stochastic",
        "rsi",
        "stddev",
        "stochrsi",
        "slope",
        "dmi",
        "adx",
        "macd",
        "atr",
        "cci",
        "sar",
        "bbands",
        "splitadjusted",
    ]
)


def execute(
    ticker: str,
    function: str,
    exchange: str = "US",
    period: int = 50,
    from_date: str | None = None,
    to_date: str | None = None,
    order: str = "a",
) -> dict[str, Any]:
    if function not in _VALID_FUNCTIONS:
        raise ValueError(
            f"Unknown technical indicator function: {function!r}. "
            f"Valid values: {sorted(_VALID_FUNCTIONS)}"
        )
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = f"&function={function}&period={period}&order={order}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    rows = client._get("technical", symbol, qs)
    return {
        "ticker": symbol,
        "function": function,
        "period": period,
        "rows": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_technical_indicators",
        category=Category.ADAPTER,
        one_liner="EODHD technical indicator series (SMA, EMA, RSI, MACD, etc.) for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch a technical indicator time series from EODHD for a ticker. "
            "Supports 19 indicator functions including SMA, EMA, RSI, MACD, Bollinger Bands, "
            "ATR, ADX, stochastic, and volatility."
        ),
        when_to_use=[
            "Generating a technical overlay for an EOD price chart.",
            "RSI or MACD readings for a momentum/trend summary.",
            "Volatility analysis using ATR or stddev.",
        ],
        when_not_to_use=[
            "Need raw price data — use eodhd_eod_prices.",
            "Need intraday indicators — compute from eodhd_intraday output.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                required=True,
                description="Ticker symbol, e.g. 'MSFT' or 'NESN.SW'.",
            ),
            "function": HelperParam(
                type="str",
                required=True,
                description=(
                    "Indicator function name. One of: avgvol, avgvolccy, sma, ema, wma, "
                    "volatility, stochastic, rsi, stddev, stochrsi, slope, dmi, adx, macd, "
                    "atr, cci, sar, bbands, splitadjusted."
                ),
            ),
            "exchange": HelperParam(
                type="str",
                required=False,
                default="US",
                description="Exchange suffix appended when ticker has no '.'. Default 'US'.",
            ),
            "period": HelperParam(
                type="int",
                required=False,
                default=50,
                description="Lookback period (2-100000). Default 50.",
            ),
            "from_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="Start date YYYY-MM-DD.",
            ),
            "to_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="End date YYYY-MM-DD.",
            ),
            "order": HelperParam(
                type="str",
                required=False,
                default="a",
                description="'a' ascending (old-to-new), 'd' descending. Default 'a'.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description=(
                    "Dict with ticker, function, period, and rows list of indicator values."
                ),
            ),
        ],
        produces_artifacts=["eodhd_technical_indicators_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.technical"],
    ),
)

register_helper(_SCHEMA, execute)
