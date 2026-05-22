"""eodhd_balance_sheet — balance sheet statements for a ticker."""

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
    balance: dict[str, Any] = financials.get("Balance_Sheet", {})
    return {
        "ticker": symbol,
        "period": period,
        "statements": balance.get(period, balance),
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_balance_sheet",
        category=Category.ADAPTER,
        one_liner="EODHD balance sheet statements (quarterly/annual) for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract the balance sheet sub-tree from the EODHD fundamentals payload. "
            "Returns either quarterly or annual statements with all line items."
        ),
        when_to_use=[
            "Ratio analysis requiring current assets, liabilities, or equity.",
            "Liquidity or leverage calculations needing balance sheet line items.",
        ],
        when_not_to_use=[
            "Need income or cash-flow data — use eodhd_income_statement or eodhd_cash_flow.",
            "Need the full fundamentals blob — use eodhd_fundamentals.",
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
                description="Balance sheet statements keyed by period date.",
            ),
        ],
        produces_artifacts=["eodhd_balance_sheet_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
)

register_helper(_SCHEMA, execute)
