from typing import Any

from openlia.data.base import ProviderAdapter
from openlia.data.manifest.types import Requirement, RequirementTier
from openlia.data.resolver import (
    ResolvedProvider,
    resolve_provider_for_capability,
    resolve_tools_for_requirements,
)
from openlia.data.types import ProviderCategory, ProviderEntry, ProviderMode, ToolResult


class _QuotesOnly(ProviderAdapter):
    kind = "quotes_only"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote"})

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


class _QuotesAndNews(ProviderAdapter):
    kind = "quotes_and_news"
    category = ProviderCategory.FINANCIAL
    capabilities = frozenset({"stock_quote", "company_news"})

    async def fetch(self, capability: str, params: dict[str, Any]) -> ToolResult:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


def _entry(kind: str, priority: int, is_enabled: bool = True) -> ProviderEntry:
    return ProviderEntry(
        id=f"{kind}-id",
        kind=kind,
        label=kind,
        category=ProviderCategory.FINANCIAL,
        mode=ProviderMode.API_KEY,
        api_key="k",
        base_url="https://example.test",
        priority=priority,
        is_enabled=is_enabled,
    )


_REGISTRY: dict[str, type[ProviderAdapter]] = {
    "quotes_only": _QuotesOnly,
    "quotes_and_news": _QuotesAndNews,
}


def test_resolver_returns_highest_priority_capable_provider() -> None:
    entries = [_entry("quotes_and_news", priority=50), _entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"  # priority 10 < 50 wins


def test_resolver_skips_provider_without_capability() -> None:
    entries = [_entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="company_news",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is None


def test_resolver_skips_disabled_provider() -> None:
    entries = [
        _entry("quotes_and_news", priority=10, is_enabled=False),
        _entry("quotes_only", priority=50),
    ]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"


def test_resolver_returns_none_when_no_provider_has_capability() -> None:
    entries = [_entry("quotes_only", priority=10)]
    assert (
        resolve_provider_for_capability(
            capability="insider_transactions",
            entries=entries,
            adapters=_REGISTRY,
        )
        is None
    )


def test_resolver_skips_unknown_kind() -> None:
    entries = [_entry("ghost", priority=10), _entry("quotes_only", priority=20)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert resolved is not None
    assert resolved.entry.kind == "quotes_only"


def test_resolve_tools_for_requirements_builds_ordered_list() -> None:
    entries = [
        _entry("quotes_and_news", priority=10),
        _entry("quotes_only", priority=20),
    ]
    requirements = [
        Requirement(type="stock_quote", description="d", tier=RequirementTier.BASIC),
        Requirement(type="company_news", description="d", tier=RequirementTier.BASIC),
        Requirement(
            type="insider_transactions",  # no provider covers this
            description="d",
            tier=RequirementTier.ADVANCED,
        ),
    ]
    resolved, unmet = resolve_tools_for_requirements(
        requirements=requirements,
        entries=entries,
        adapters=_REGISTRY,
    )
    # Two requirements resolved; 'insider_transactions' is unmet
    by_cap = {r.capability: r for r in resolved}
    assert set(by_cap) == {"stock_quote", "company_news"}
    assert by_cap["stock_quote"].entry.kind == "quotes_and_news"  # priority 10
    assert by_cap["company_news"].entry.kind == "quotes_and_news"
    assert unmet == ["insider_transactions"]


def test_resolved_provider_carries_adapter_class() -> None:
    entries = [_entry("quotes_only", priority=10)]
    resolved = resolve_provider_for_capability(
        capability="stock_quote",
        entries=entries,
        adapters=_REGISTRY,
    )
    assert isinstance(resolved, ResolvedProvider)
    assert resolved.adapter_cls is _QuotesOnly
