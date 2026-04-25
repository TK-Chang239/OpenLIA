"""Adapter registry.

Maps `kind` strings (as stored in data_providers.kind) to adapter classes.
Server code uses this to look up the right adapter when instantiating a
ProviderAdapter from a ProviderEntry.

Plan 3 ships a working EODHDAdapter plus stubs for FMP, Finnhub, yfinance,
NewsAPI.ai, NewsAPI.org, and Mediastack. Stubs let admins create rows and
exercise auto-map; their `fetch` raises DataNotAvailable until a future
phase implements the integration.
"""

from openlia.data.adapters._stub import (
    FinnhubAdapter,
    FMPAdapter,
    MediastackAdapter,
    NewsAPIAIAdapter,
    NewsAPIOrgAdapter,
    YFinanceAdapter,
)
from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.base import ProviderAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    EODHDAdapter.kind: EODHDAdapter,
    FMPAdapter.kind: FMPAdapter,
    FinnhubAdapter.kind: FinnhubAdapter,
    YFinanceAdapter.kind: YFinanceAdapter,
    NewsAPIAIAdapter.kind: NewsAPIAIAdapter,
    NewsAPIOrgAdapter.kind: NewsAPIOrgAdapter,
    MediastackAdapter.kind: MediastackAdapter,
}

__all__ = [
    "ADAPTERS",
    "EODHDAdapter",
    "FMPAdapter",
    "FinnhubAdapter",
    "MediastackAdapter",
    "NewsAPIAIAdapter",
    "NewsAPIOrgAdapter",
    "YFinanceAdapter",
]
