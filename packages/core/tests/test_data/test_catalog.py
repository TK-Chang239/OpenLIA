"""Tests for the provider catalog snapshot."""

from openlia.data.adapters import ADAPTERS
from openlia.data.adapters.eodhd import EODHDAdapter
from openlia.data.adapters.fmp import FMPAdapter
from openlia.data.catalog import CatalogEntry, ProviderCatalog, build_catalog
from openlia.data.types import ProviderCategory


def test_build_catalog_uses_live_registry_by_default() -> None:
    catalog = build_catalog()
    kinds = catalog.kinds()
    for known in ("eodhd", "fmp", "finnhub", "yfinance", "newsapi_org", "mediastack"):
        assert known in kinds


def test_catalog_entries_are_sorted_by_kind() -> None:
    catalog = build_catalog()
    kinds = catalog.kinds()
    assert list(kinds) == sorted(kinds)


def test_catalog_entry_carries_capabilities_and_category() -> None:
    catalog = build_catalog({"eodhd": EODHDAdapter})
    entry = catalog.find("eodhd")
    assert entry is not None
    assert entry.category is ProviderCategory.FINANCIAL
    assert "stock_quote" in entry.capabilities
    assert tuple(entry.capabilities) == tuple(sorted(entry.capabilities))


def test_catalog_find_returns_none_for_unknown_kind() -> None:
    catalog = build_catalog({"eodhd": EODHDAdapter})
    assert catalog.find("polygon") is None


def test_catalog_includes_stub_adapters_with_empty_capabilities() -> None:
    """Stub adapters declare an empty `capabilities` frozenset.

    The catalog must surface that as an empty tuple — not omit them — so the
    review flow can distinguish "registered but covers nothing" from
    "unregistered/unknown".
    """
    catalog = build_catalog()
    reddit = catalog.find("reddit")
    assert reddit is not None
    assert reddit.capabilities == ()


def test_explicit_adapters_arg_isolates_from_live_registry() -> None:
    catalog = build_catalog({"fmp": FMPAdapter})
    assert catalog.kinds() == ("fmp",)


def test_catalog_models_are_frozen() -> None:
    catalog = build_catalog({"eodhd": EODHDAdapter})
    entry = catalog.find("eodhd")
    assert isinstance(entry, CatalogEntry)
    assert isinstance(catalog, ProviderCatalog)
    import pydantic

    try:
        entry.kind = "other"  # type: ignore[misc]
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("CatalogEntry should be frozen")


def test_catalog_covers_every_registered_adapter() -> None:
    catalog = build_catalog()
    assert len(catalog.entries) == len(ADAPTERS)
