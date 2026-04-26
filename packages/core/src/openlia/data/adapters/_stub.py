"""Deferred-implementation adapter stubs.

Each registers a `kind` so admins can create DataProvider rows for them
through `/settings/data-providers` (auto-map will then list their
capabilities as unmet). Calling `fetch` always raises DataNotAvailable.
Implementation is owned by a future phase per data-provider-design.md.
"""

from typing import Any, ClassVar

from openlia.data.base import ProviderAdapter
from openlia.data.errors import DataNotAvailable
from openlia.data.types import ProviderCategory, ToolResult


class _StubAdapter(ProviderAdapter):
    """Base for adapters whose implementation is deferred."""

    capabilities: ClassVar[frozenset[str]] = frozenset()

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise DataNotAvailable(
            provider_kind=self.kind,
            capability=capability,
            reason=f"adapter {self.kind!r} is a registry stub; implementation deferred",
        )

    async def health_check(self) -> bool:
        return False


class RedditAdapter(_StubAdapter):
    kind: ClassVar[str] = "reddit"
    category: ClassVar[ProviderCategory] = ProviderCategory.SOCIAL_MEDIA


class XAdapter(_StubAdapter):
    kind: ClassVar[str] = "x"
    category: ClassVar[ProviderCategory] = ProviderCategory.SOCIAL_MEDIA


class BraveSearchAdapter(_StubAdapter):
    kind: ClassVar[str] = "brave"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH


class TavilyAdapter(_StubAdapter):
    kind: ClassVar[str] = "tavily"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH


class SerperAdapter(_StubAdapter):
    kind: ClassVar[str] = "serper"
    category: ClassVar[ProviderCategory] = ProviderCategory.SEARCH
