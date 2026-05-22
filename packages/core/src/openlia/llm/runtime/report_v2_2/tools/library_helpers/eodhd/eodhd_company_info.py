"""eodhd_company_info — company profile / general information for a ticker."""

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
    data = client._get("fundamentals", symbol)
    general: dict[str, Any] = data.get("General", {})
    return {
        "ticker": symbol,
        "general": general,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_company_info",
        category=Category.ADAPTER,
        one_liner="EODHD company profile: name, description, sector, industry, exchange.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract the General section from the EODHD fundamentals payload. "
            "Returns company name, description, sector, industry, exchange, country, "
            "fiscal year end, IPO date, and employee count."
        ),
        when_to_use=[
            "Populating a company overview or header section.",
            "Determining GICS sector/industry for routing or comparables.",
        ],
        when_not_to_use=[
            "Need financial statements — use eodhd_income_statement, "
            "eodhd_balance_sheet, or eodhd_cash_flow.",
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
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker and general company profile fields.",
            ),
        ],
        produces_artifacts=["eodhd_company_info_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
)

register_helper(_SCHEMA, execute)
