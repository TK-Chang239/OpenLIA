"""eodhd_intraday — intraday OHLCV bars for a ticker."""

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


def execute(
    ticker: str,
    exchange: str = "US",
    interval: str = "5m",
    from_unix: str | None = None,
    to_unix: str | None = None,
) -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = f"&interval={interval}"
    if from_unix:
        qs += f"&from={from_unix}"
    if to_unix:
        qs += f"&to={to_unix}"
    rows = client._get("intraday", symbol, qs)
    return {
        "ticker": symbol,
        "interval": interval,
        "rows": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_intraday",
        category=Category.ADAPTER,
        one_liner="EODHD intraday OHLCV bars at 1m, 5m, or 1h for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch intraday price bars from EODHD for a ticker. "
            "Supports 1-minute, 5-minute, and 1-hour intervals. "
            "Use for same-day volatility analysis or intraday pattern detection."
        ),
        when_to_use=[
            "Intraday volatility or VWAP calculations.",
            "Same-day price movement analysis.",
        ],
        when_not_to_use=[
            "Daily/weekly/monthly prices — use eodhd_eod_prices.",
            "Live last price — use eodhd_real_time_quote.",
        ],
    ),
    contract=MechanicalContract(
        params={
            "ticker": HelperParam(
                type="str",
                required=True,
                description="Ticker symbol, e.g. 'MSFT' or 'NESN.SW'.",
            ),
            "exchange": HelperParam(
                type="str",
                required=False,
                default="US",
                description="Exchange suffix appended when ticker has no '.'. Default 'US'.",
            ),
            "interval": HelperParam(
                type="str",
                required=False,
                default="5m",
                description="'1m', '5m', or '1h'. Default '5m'.",
            ),
            "from_unix": HelperParam(
                type="str",
                required=False,
                default=None,
                description="Start time as Unix timestamp string. Omit for default window.",
            ),
            "to_unix": HelperParam(
                type="str",
                required=False,
                default=None,
                description="End time as Unix timestamp string. Omit for now.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker, interval, and rows list of intraday OHLCV dicts.",
            ),
        ],
        produces_artifacts=["eodhd_intraday_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.intraday"],
    ),
)

register_helper(_SCHEMA, execute)
