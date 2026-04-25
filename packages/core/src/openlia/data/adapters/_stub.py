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


class FMPAdapter(_StubAdapter):
    kind: ClassVar[str] = "fmp"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL


class FinnhubAdapter(_StubAdapter):
    kind: ClassVar[str] = "finnhub"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL


class YFinanceAdapter(_StubAdapter):
    kind: ClassVar[str] = "yfinance"
    category: ClassVar[ProviderCategory] = ProviderCategory.FINANCIAL


class NewsAPIAIAdapter(_StubAdapter):
    kind: ClassVar[str] = "newsapi_ai"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS


class NewsAPIOrgAdapter(_StubAdapter):
    kind: ClassVar[str] = "newsapi_org"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS


class MediastackAdapter(_StubAdapter):
    kind: ClassVar[str] = "mediastack"
    category: ClassVar[ProviderCategory] = ProviderCategory.NEWS
