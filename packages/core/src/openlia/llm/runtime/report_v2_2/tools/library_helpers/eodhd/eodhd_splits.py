"""eodhd_splits — historical stock split history for a ticker."""

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
    rows = client._get("splits", symbol, qs)
    return {
        "ticker": symbol,
        "splits": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_splits",
        category=Category.ADAPTER,
        one_liner="EODHD historical stock split history for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the complete stock split history from EODHD for a ticker. "
            "Returns split date and split ratio for each event."
        ),
        when_to_use=[
            "Verifying price-series adjust factors when computing long-term returns.",
            "Reporting split history in a company timeline section.",
        ],
        when_not_to_use=[
            "Need dividend history — use eodhd_dividends.",
            "EOD prices already return adjusted close — use eodhd_eod_prices "
            "for split-adjusted series.",
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
                description="Dict with ticker and splits list of {date, split} records.",
            ),
        ],
        produces_artifacts=["eodhd_splits_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.splits"],
    ),
)

register_helper(_SCHEMA, execute)
