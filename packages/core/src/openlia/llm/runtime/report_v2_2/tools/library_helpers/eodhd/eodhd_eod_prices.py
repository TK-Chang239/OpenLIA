"""eodhd_eod_prices — end-of-day OHLCV price series for a ticker."""

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
    period: str = "d",
    from_date: str | None = None,
    to_date: str | None = None,
    order: str = "a",
) -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = f"&period={period}&order={order}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    rows = client._get("eod", symbol, qs)
    return {
        "ticker": symbol,
        "period": period,
        "from_date": from_date,
        "to_date": to_date,
        "rows": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_eod_prices",
        category=Category.ADAPTER,
        one_liner="EODHD end-of-day OHLCV price series (daily/weekly/monthly) for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the EOD OHLCV time series from EODHD for a ticker. "
            "Supports daily, weekly, and monthly aggregation. "
            "Use for price-based analysis: momentum, returns, chart building."
        ),
        when_to_use=[
            "Computing historical returns or price momentum.",
            "Building price charts or technical overlays.",
            "Volatility and beta calculations requiring a price series.",
        ],
        when_not_to_use=[
            "Need live/delayed prices — use eodhd_real_time_quote.",
            "Need intraday bars — use eodhd_intraday.",
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
            "period": HelperParam(
                type="str",
                required=False,
                default="d",
                description="'d' daily, 'w' weekly, 'm' monthly. Default 'd'.",
            ),
            "from_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="Start date YYYY-MM-DD. Omit for maximum history.",
            ),
            "to_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="End date YYYY-MM-DD. Omit for today.",
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
                    "Dict with ticker, period, from_date, to_date, and rows list of OHLCV dicts."
                ),
            ),
        ],
        produces_artifacts=["eodhd_eod_prices_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.eod"],
    ),
)

register_helper(_SCHEMA, execute)
