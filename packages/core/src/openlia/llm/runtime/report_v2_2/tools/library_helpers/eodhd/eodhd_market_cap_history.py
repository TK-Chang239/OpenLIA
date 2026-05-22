"""eodhd_market_cap_history — historical market capitalization series for a ticker."""

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
    from_date: str | None = None,
    to_date: str | None = None,
) -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = ""
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    rows = client._get("historical-market-cap", symbol, qs)
    return {
        "ticker": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "market_cap_history": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_market_cap_history",
        category=Category.ADAPTER,
        one_liner="EODHD historical market capitalization series for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the daily historical market cap series from EODHD for a ticker. "
            "Use for enterprise value calculations, size-based comparisons, or "
            "tracking valuation expansion/contraction over time."
        ),
        when_to_use=[
            "Plotting market cap trend over 1-5 year periods.",
            "EV calculations requiring historical market cap as a component.",
        ],
        when_not_to_use=[
            "Need current market cap only — it is in eodhd_fundamentals Highlights.",
            "Need price series — use eodhd_eod_prices.",
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
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description=(
                    "Dict with ticker and market_cap_history list "
                    "of {date, marketCapitalization} records."
                ),
            ),
        ],
        produces_artifacts=["eodhd_market_cap_history_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.historical-market-cap"],
    ),
)

register_helper(_SCHEMA, execute)
