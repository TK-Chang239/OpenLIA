"""eodhd_fundamentals — full fundamentals snapshot for a ticker."""

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
    return client._get("fundamentals", symbol)


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_fundamentals",
        category=Category.ADAPTER,
        one_liner="Full EODHD fundamentals snapshot: financials, valuation, earnings, ratings.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch the complete fundamentals payload from EODHD for a ticker. "
            "Covers General, Highlights, Valuation, Financials (income/balance/cash-flow), "
            "Earnings history, and analyst ratings in one call."
        ),
        when_to_use=[
            "Need a broad financial snapshot to seed multiple downstream helpers.",
            "Fetching valuation highlights (P/E, P/B, EV/EBITDA) in one call.",
            "Retrieving analyst target prices and ratings.",
        ],
        when_not_to_use=[
            "Need only a specific statement — use eodhd_income_statement, "
            "eodhd_balance_sheet, or eodhd_cash_flow to avoid a large payload.",
            "Need live pricing — use eodhd_real_time_quote instead.",
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
                description="Full EODHD fundamentals JSON for the ticker.",
            ),
        ],
        produces_artifacts=["eodhd_fundamentals_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
)

register_helper(_SCHEMA, execute)
