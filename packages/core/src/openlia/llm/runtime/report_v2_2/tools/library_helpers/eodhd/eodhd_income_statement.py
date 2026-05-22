"""eodhd_income_statement — income statement for a ticker."""

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


def execute(ticker: str, exchange: str = "US", period: str = "quarterly") -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    data = client._get("fundamentals", symbol)
    financials: dict[str, Any] = data.get("Financials", {})
    income: dict[str, Any] = financials.get("Income_Statement", {})
    return {
        "ticker": symbol,
        "period": period,
        "statements": income.get(period, income),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_income_statement",
        category=Category.ADAPTER,
        one_liner="EODHD income statement (quarterly/annual) for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract the income statement sub-tree from the EODHD fundamentals payload. "
            "Returns quarterly or annual statements with revenue, gross profit, operating "
            "income, net income, and EPS."
        ),
        when_to_use=[
            "Revenue trend analysis or margin calculations.",
            "EPS history for earnings quality assessment.",
        ],
        when_not_to_use=[
            "Need balance sheet data — use eodhd_balance_sheet.",
            "Need cash flow data — use eodhd_cash_flow.",
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
                default="quarterly",
                description="'quarterly' or 'annual'. Default 'quarterly'.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Income statement records keyed by period date.",
            ),
        ],
        produces_artifacts=["eodhd_income_statement_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
)

register_helper(_SCHEMA, execute)
