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

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol, runtime_checkable

from openlia.llm.types import ResolvedModel

_TRUTHY = {"1", "true", "yes", "on"}
_FALSY = {"0", "false", "no", "off"}


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in _TRUTHY:
        return True
    if v in _FALSY:
        return False
    return default


def native_web_search_enabled() -> bool:
    """Resolve the two env flags that gate native web search.

    OPENLIA_DISABLE_NATIVE_WEB_SEARCH wins (emergency kill switch).
    OPENLIA_NATIVE_WEB_SEARCH defaults true (the migration flag is left
    on once a deployment has soaked).
    """
    if _env_bool("OPENLIA_DISABLE_NATIVE_WEB_SEARCH", default=False):
        return False
    return _env_bool("OPENLIA_NATIVE_WEB_SEARCH", default=True)


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
    if resolved.capabilities.web_search_native and native_web_search_enabled():
        return WebSearchResolution(available=True, variant="native", adapter=None)
    adapter = search_adapter_factory()
    if adapter is not None:
        return WebSearchResolution(available=True, variant="configured", adapter=adapter)
    return WebSearchResolution(available=False, variant=None, adapter=None)
