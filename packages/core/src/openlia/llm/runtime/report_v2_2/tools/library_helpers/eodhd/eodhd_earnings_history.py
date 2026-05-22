"""eodhd_earnings_history — historical EPS actuals and estimates for a ticker."""

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
    earnings: dict[str, Any] = data.get("Earnings", {})
    history: Any = earnings.get("History", {})
    annual: Any = earnings.get("Annual", {})
    return {
        "ticker": symbol,
        "quarterly_history": history,
        "annual_history": annual,
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_earnings_history",
        category=Category.ADAPTER,
        one_liner="EODHD historical EPS actuals vs estimates with surprise per quarter.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Extract quarterly and annual earnings history from the EODHD fundamentals payload. "
            "Returns EPS actual, EPS estimate, and beat/miss surprise per reporting period."
        ),
        when_to_use=[
            "Earnings quality and consistency analysis.",
            "Building an EPS trend chart or earnings surprise table.",
        ],
        when_not_to_use=[
            "Need upcoming earnings dates — use eodhd_upcoming_earnings.",
            "Need earnings trend/analyst estimates — use eodhd_upcoming_earnings with symbols.",
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
                    "Dict with ticker, quarterly_history, and annual_history earnings records."
                ),
            ),
        ],
        produces_artifacts=["eodhd_earnings_history_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.fundamentals"],
    ),
)

register_helper(_SCHEMA, execute)
