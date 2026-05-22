"""eodhd_news — recent financial news articles for a ticker."""

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
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    symbol = f"{ticker}.{exchange}" if "." not in ticker else ticker
    qs = f"&s={symbol}&limit={limit}&offset={offset}"
    if from_date:
        qs += f"&from={from_date}"
    if to_date:
        qs += f"&to={to_date}"
    rows = client._get("news", querystring=qs)
    return {
        "ticker": symbol,
        "articles": rows if isinstance(rows, list) else [],
    }


_SCHEMA = HelperSchema(
    version="0.1.0",
    directory=DirectoryEntry(
        name="eodhd_news",
        category=Category.ADAPTER,
        one_liner="EODHD recent financial news articles for a single ticker.",
    ),
    selection=SelectionGuidance(
        purpose=(
            "Fetch recent news articles from EODHD for a ticker. "
            "Returns title, link, publication date, and summary. "
            "Use as input for NLP/sentiment analysis or to populate a news digest section."
        ),
        when_to_use=[
            "Populating a 'Recent News' section of a report.",
            "Providing article text to an NLP helper for summarization or sentiment.",
        ],
        when_not_to_use=[
            "Need quantitative sentiment scores — use eodhd_sentiment.",
            "Need macro/market-wide news — filter by topic tag in the EODHD news API directly.",
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
                default=50,
                description="Max articles returned (1-1000). Default 50.",
            ),
            "offset": HelperParam(
                type="int",
                required=False,
                default=0,
                description="Pagination offset. Default 0.",
            ),
        },
        outputs=[
            HelperOutput(
                name="data",
                type="dict",
                description="Dict with ticker and articles list of news records.",
            ),
        ],
        produces_artifacts=["eodhd_news_output"],
        consumes_artifacts=[],
        data_dependencies=["eodhd.news"],
    ),
)

register_helper(_SCHEMA, execute)
