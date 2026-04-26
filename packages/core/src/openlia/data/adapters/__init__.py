"""Adapter registry.

Maps `kind` strings (as stored in data_providers.kind) to adapter classes.
Server code uses this to look up the right adapter when instantiating a
ProviderAdapter from a ProviderEntry.

Financial (eodhd, fmp, finnhub, yfinance) and news (newsapi_ai, newsapi_org,
mediastack) adapters ship with full HTTP implementations. Social-media and
search adapters remain registry stubs (`reddit`, `x`, `brave`, `tavily`,
`serper`) — admins can configure rows for them and auto-map will list their
capabilities as unmet, but `fetch` raises DataNotAvailable until a future
phase implements the integration.
"""

from openlia.data.adapters._stub import (
    BraveSearchAdapter,
    RedditAdapter,
    SerperAdapter,
    TavilyAdapter,
    XAdapter,
)
from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.adapters.finnhub import FinnhubAdapter
from openlia.data.adapters.fmp import FMPAdapter
from openlia.data.adapters.mediastack import MediastackAdapter
from openlia.data.adapters.newsapi_ai import NewsAPIAIAdapter
from openlia.data.adapters.newsapi_org import NewsAPIOrgAdapter
from openlia.data.adapters.yfinance import YFinanceAdapter
from openlia.data.base import ProviderAdapter

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    EODHDAdapter.kind: EODHDAdapter,
    FMPAdapter.kind: FMPAdapter,
    FinnhubAdapter.kind: FinnhubAdapter,
    YFinanceAdapter.kind: YFinanceAdapter,
    NewsAPIAIAdapter.kind: NewsAPIAIAdapter,
    NewsAPIOrgAdapter.kind: NewsAPIOrgAdapter,
    MediastackAdapter.kind: MediastackAdapter,
    RedditAdapter.kind: RedditAdapter,
    XAdapter.kind: XAdapter,
    BraveSearchAdapter.kind: BraveSearchAdapter,
    TavilyAdapter.kind: TavilyAdapter,
    SerperAdapter.kind: SerperAdapter,
}

__all__ = [
    "ADAPTERS",
    "BraveSearchAdapter",
    "EODHDAdapter",
    "FMPAdapter",
    "FinnhubAdapter",
    "MediastackAdapter",
    "NewsAPIAIAdapter",
    "NewsAPIOrgAdapter",
    "RedditAdapter",
    "SerperAdapter",
    "TavilyAdapter",
    "XAdapter",
    "YFinanceAdapter",
]
