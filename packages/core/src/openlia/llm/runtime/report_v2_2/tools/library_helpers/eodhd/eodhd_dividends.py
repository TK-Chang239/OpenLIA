"""eodhd_dividends — historical dividend payment history for a ticker."""

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
    rows = client._get("div", symbol, qs)
    return {
        "ticker": symbol,
        "from_date": from_date,
        "to_date": to_date,
        "dividends": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_dividends",
        category=Category.ADAPTER,
        one_liner="EODHD historical dividend payment history for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the complete dividend payment history from EODHD for a ticker. "
            "Returns payment date, declaration date, record date, ex-dividend date, and amount."
        ),
        when_to_use=[
            "Dividend yield calculations or income analysis.",
            "Dividend growth rate trend analysis.",
            "Checking dividend consistency and sustainability.",
        ],
        when_not_to_use=[
            "Need upcoming dividend dates — use eodhd_upcoming_earnings for the earnings calendar.",
            "Need split history — use eodhd_splits.",
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
                description="Dict with ticker and dividends list of payment records.",
            ),
        ],
        produces_artifacts=["eodhd_dividends_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.div"],
    ),
)

register_helper(_SCHEMA, execute)
