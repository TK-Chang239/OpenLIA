"""Adapter registry.

Maps `kind` strings (as stored in data_providers.kind) to adapter classes.
Server code uses this to look up the right adapter when instantiating a
ProviderAdapter from a ProviderEntry.

Financial (eodhd, fmp, finnhub, yfinance), news (newsapi_ai, newsapi_org,
mediastack), social-media (reddit, x), and search (brave, tavily, serper)
adapters all ship with full HTTP implementations modelled on the providers'
official MCP servers (or, where no first-party MCP exists, on the providers'
documented REST APIs).

The legacy `_StubAdapter` base remains importable for backward-compatible
tests that key off `issubclass(..., _StubAdapter)`; no concrete adapter
inherits from it any more.
"""

from openlia.data.adapters.brave import BraveSearchAdapter
from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.adapters.finnhub import FinnhubAdapter
from openlia.data.adapters.firecrawl import FirecrawlAdapter
from openlia.data.adapters.fmp import FMPAdapter
from openlia.data.adapters.mediastack import MediastackAdapter
from openlia.data.adapters.newsapi_ai import NewsAPIAIAdapter
from openlia.data.adapters.newsapi_org import NewsAPIOrgAdapter
from openlia.data.adapters.reddit import RedditAdapter
from openlia.data.adapters.serper import SerperAdapter
from openlia.data.adapters.tavily import TavilyAdapter
from openlia.data.adapters.x import XAdapter
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
    FirecrawlAdapter.kind: FirecrawlAdapter,
}

__all__ = [
    "ADAPTERS",
    "BraveSearchAdapter",
    "EODHDAdapter",
    "FMPAdapter",
    "FinnhubAdapter",
    "FirecrawlAdapter",
    "MediastackAdapter",
    "NewsAPIAIAdapter",
    "NewsAPIOrgAdapter",
    "RedditAdapter",
    "SerperAdapter",
    "TavilyAdapter",
    "XAdapter",
    "YFinanceAdapter",
]
