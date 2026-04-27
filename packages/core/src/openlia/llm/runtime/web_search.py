"""Web search resolution.

The runtime sees web search through one abstraction: `WebSearchResolution`
with `available` and `variant` ("native"). When `native`, the tool is
handed to the provider via `LLMRequest.tools` with a provider-specific
name (the adapter layer recognizes `web_search` and swaps in the native
tool). The "configured" variant — where a separate adapter implemented
`adapter.search(query)` — was retired in the connector cutover; configured
search is now a normal `web_search`-category Connector dispatched through
`Dispatcher` like every other tool.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from openlia.llm.types import ResolvedModel


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


@runtime_checkable
class WebSearchAdapter(Protocol):
    """Structural contract for a configured web-search provider."""

    async def search(self, query: str) -> list[WebSearchResult]: ...


@dataclass(frozen=True)
class WebSearchResolution:
    available: bool
    variant: Literal["native", "configured"] | None
    adapter: WebSearchAdapter | None


def resolve_web_search(
    *,
    resolved: ResolvedModel,
    search_adapter_factory: Callable[[], WebSearchAdapter | None],
) -> WebSearchResolution:
    """Pick native-first, then configured, then unavailable."""
    if resolved.capabilities.web_search_native:
        return WebSearchResolution(available=True, variant="native", adapter=None)
    adapter = search_adapter_factory()
    if adapter is not None:
        return WebSearchResolution(available=True, variant="configured", adapter=adapter)
    return WebSearchResolution(available=False, variant=None, adapter=None)
