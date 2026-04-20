"""Web search resolution.

The runtime sees web search through one abstraction: `WebSearchResolution`
with `available`, `variant` ("native" | "configured"), and an optional
`adapter`. When `native`, the tool is handed to the provider via
`LLMRequest.tools` with a provider-specific name (the adapter layer
recognizes `web_search` and swaps in the native tool). When `configured`,
`ToolDispatcher.dispatch()` calls `adapter.search(query)`.

The server layer builds the adapter factory from the `search` data-provider
category (Brave / Tavily / Serper / You.com) and passes it in. The runtime
never reads DB state directly.
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
