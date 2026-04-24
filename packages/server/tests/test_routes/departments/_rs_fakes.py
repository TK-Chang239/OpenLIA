"""Shared fakes for retail sentiment route tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class FakeRsDataProvider:
    """In-memory data provider returning pre-canned post lists per ticker."""

    def __init__(self, payloads: dict[tuple[str, str], Any] | None = None) -> None:
        self._payloads = payloads or {}

    def fetch(self, *, requirement: str, ticker: str, **kwargs: Any) -> Any:
        return self._payloads.get((ticker, requirement))

    @classmethod
    def with_default_posts(cls, ticker: str = "AAPL") -> FakeRsDataProvider:
        now = datetime(2026, 4, 23, 12, 0, tzinfo=UTC).isoformat()
        posts = [
            {
                "id": f"p{i}",
                "text": f"bullish news {i}",
                "source": "social_media",
                "created_at": now,
            }
            for i in range(5)
        ]
        news = [{"id": f"n{i}", "title": f"news headline {i}", "created_at": now} for i in range(3)]
        return cls(payloads={(ticker, "social_sentiment"): posts, (ticker, "company_news"): news})
