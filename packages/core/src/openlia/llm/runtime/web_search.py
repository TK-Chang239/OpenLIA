"""Web search resolution.

The runtime sees web search through one abstraction: `WebSearchResolution`
with `available` and `variant="native"`. When `native`, the tool is handed
to the provider via `LLMRequest.tools` with a provider-specific name (the
adapter layer recognizes `web_search` and swaps in the native tool). The
"configured" variant — where a separate adapter implemented
`adapter.search(query)` — was retired in the connector cutover; configured
search is now a normal `web_search`-category Connector dispatched through
`Dispatcher` like every other tool.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebSearchResolution:
    available: bool
    variant: Literal["native"] | None
