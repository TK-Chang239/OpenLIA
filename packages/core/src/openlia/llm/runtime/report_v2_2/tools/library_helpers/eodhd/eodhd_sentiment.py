"""eodhd_sentiment — sentiment scores for a ticker over a date range."""

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
    qs = f"&s={symbol}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    data = client._get("sentiments", querystring=qs)
    return {
        "ticker": symbol,
        "sentiment": data if isinstance(data, (list, dict)) else {},
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_sentiment",
        category=Category.ADAPTER,
        one_liner="EODHD quantitative sentiment scores for a ticker over a date range.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch normalized news sentiment scores from EODHD for a ticker. "
            "Returns a score (typically -1 to 1) and article count per date. "
            "Use as a signal layer alongside price and fundamental analysis."
        ),
        when_to_use=[
            "Detecting sentiment divergence from price action.",
            "Building a sentiment trend chart for a report signals section.",
        ],
        when_not_to_use=[
            "Need raw article text — use eodhd_news.",
            "Need social media / Reddit sentiment — not in this endpoint.",
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
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker and sentiment data (list or dict by date).",
            ),
        ],
        produces_artifacts=["eodhd_sentiment_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.sentiments"],
    ),
)

register_helper(_SCHEMA, execute)
