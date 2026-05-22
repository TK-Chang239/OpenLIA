"""eodhd_upcoming_earnings — upcoming earnings calendar for a ticker."""

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
    # EODHD upcoming earnings endpoint: /calendar/earnings?symbols=<ticker>
    qs = f"&symbols={symbol}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    data = client._get("calendar/earnings", querystring=qs)
    earnings_list: list[Any] = []
    if isinstance(data, dict):
        earnings_list = data.get("earnings", [])
    elif isinstance(data, list):
        earnings_list = data
    return {
        "ticker": symbol,
        "upcoming_earnings": earnings_list,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_upcoming_earnings",
        category=Category.ADAPTER,
        one_liner="EODHD upcoming earnings calendar dates and estimates for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch upcoming earnings events from EODHD for a ticker or date range. "
            "Returns next report date, EPS estimate, and revenue estimate. "
            "Use for event-risk flagging in reports."
        ),
        when_to_use=[
            "Adding an upcoming earnings event-risk notice to a report.",
            "Checking whether earnings fall within a report's forecast horizon.",
        ],
        when_not_to_use=[
            "Need historical EPS actuals — use eodhd_earnings_history.",
            "Need analyst consensus detail — use eodhd_fundamentals AnalystRatings section.",
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
                description="Start date YYYY-MM-DD. Omit for today.",
            ),
            "to_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="End date YYYY-MM-DD. Omit for today + 7 days.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker and upcoming_earnings list of event records.",
            ),
        ],
        produces_artifacts=["eodhd_upcoming_earnings_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.calendar/earnings"],
    ),
)

register_helper(_SCHEMA, execute)
