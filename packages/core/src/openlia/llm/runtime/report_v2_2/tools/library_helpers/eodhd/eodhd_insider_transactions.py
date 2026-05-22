"""eodhd_insider_transactions — insider trading transactions for a ticker."""

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
    limit: int = 100,
) -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = f"&code={symbol}&limit={limit}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    rows = client._get("insider-transactions", querystring=qs)
    return {
        "ticker": symbol,
        "transactions": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_insider_transactions",
        category=Category.ADAPTER,
        one_liner="EODHD insider trading transactions for a ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch insider buy/sell transactions from EODHD for a ticker. "
            "Returns transaction date, insider name, title, transaction type, shares, and value."
        ),
        when_to_use=[
            "Governance review: checking for unusual insider selling patterns.",
            "Sentiment signal: large insider buying as a bullish indicator.",
        ],
        when_not_to_use=[
            "Need short interest data — not available via this endpoint.",
            "Need institutional ownership — use eodhd_fundamentals SharesStats section.",
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
                description="Start date YYYY-MM-DD.",
            ),
            "to_date": HelperParam(
                type="str",
                required=False,
                default=None,
                description="End date YYYY-MM-DD.",
            ),
            "limit": HelperParam(
                type="int",
                required=False,
                default=100,
                description="Max transactions returned (1-1000). Default 100.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker and transactions list of insider trade records.",
            ),
        ],
        produces_artifacts=["eodhd_insider_transactions_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.insider-transactions"],
    ),
)

register_helper(_SCHEMA, execute)
