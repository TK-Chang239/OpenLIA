"""eodhd_real_time_quote — live/last-trade quote for a ticker."""

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


def execute(ticker: str, exchange: str = "US") -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    data = client._get("real-time", symbol)
    return data if isinstance(data, dict) else {"code": symbol, "raw": data}


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_real_time_quote",
        category=Category.ADAPTER,
        one_liner="EODHD live/delayed quote: last price, change, volume for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the most recent trade quote from EODHD for a ticker. "
            "Returns last price, open, high, low, volume, change, and percent change. "
            "Data may be delayed 15-20 minutes for non-premium subscriptions."
        ),
        when_to_use=[
            "Current price context for a report header or valuation snapshot.",
            "Checking today's open/high/low before markets close.",
        ],
        when_not_to_use=[
            "Historical EOD series — use eodhd_eod_prices.",
            "Intraday bars — use eodhd_intraday.",
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
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description=(
                    "Live quote dict: code, close, open, high, low, volume, change, change_p."
                ),
            ),
        ],
        produces_artifacts=["eodhd_real_time_quote_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.real-time"],
    ),
)

register_helper(_SCHEMA, execute)
