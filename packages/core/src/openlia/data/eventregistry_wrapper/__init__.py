"""Wraps Event Registry's `eventregistry` SDK with a simple, kwarg-only
interface usable by the connector subsystem's python_lib transport.

The native SDK's `EventRegistry.execQuery(query: QueryParamsBase)` takes
a constructed Query object — the transport (`call_tool(name, **kwargs)`)
can only pass primitives. This wrapper builds the QueryArticlesIter
internally and exposes a kwargs-only `geopolitical_news(window_days,
limit)` method that returns a flat `list[dict]` of articles.

Topic keywords are baked in (geopolitical conflict + reserve-policy
themes) because the macro_research `geopolitical_news` runner need
declares only `window_days` and `limit` as runtime parameters — the
topic intent is fixed by the World Order dashboard's narrative-context
layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from eventregistry import EventRegistry, QueryArticlesIter, QueryItems

_GEOPOLITICAL_KEYWORDS: tuple[str, ...] = (
    "geopolitical",
    "sanctions",
    "central bank",
    "reserve currency",
    "trade war",
    "tariff",
    "war",
    "military",
)


class EventRegistryWrapper(EventRegistry):
    """`eventregistry.EventRegistry` plus a kwargs-only wrapper for the
    macro_research `geopolitical_news` runner need.
    """

    def geopolitical_news(self, window_days: int = 7, limit: int = 25) -> list[dict[str, Any]]:
        """Recent geopolitical-conflict and reserve-policy headlines.

        Date window is `window_days` back from now; results are sorted
        by publish date desc and capped at `limit` items.
        """
        date_start = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime(
            "%Y-%m-%d",
        )
        q = QueryArticlesIter(
            keywords=QueryItems.OR(list(_GEOPOLITICAL_KEYWORDS)),
            dateStart=date_start,
            lang="eng",
            keywordsLoc="title,body",
        )
        articles: list[dict[str, Any]] = []
        for art in q.execQuery(self, sortBy="date", sortByAsc=False, maxItems=limit):
            articles.append(cast(dict[str, Any], art))
            if len(articles) >= limit:
                break
        return articles


__all__ = ["EventRegistryWrapper"]
