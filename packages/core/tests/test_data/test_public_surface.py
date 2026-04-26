"""P1-3-12 + NEW-3-01 — verify the openlia.data public surface."""

import importlib

import openlia.data as data


def test_public_surface_exports_all() -> None:
    expected = {
        "ADAPTERS",
        "AuthenticationError",
        "DataNotAvailable",
        "DataProviderError",
        "DataSourceError",
        "DepartmentManifest",
        "ProviderAdapter",
        "ProviderCategory",
        "ProviderEntry",
        "ProviderMode",
        "RateLimitError",
        "Requirement",
        "RequirementTier",
        "RequirementsManifest",
        "ResolvedProvider",
        "ToolResult",
        "load_manifest",
        "load_manifest_from_path",
        "resolve_provider_for_capability",
        "resolve_tools_for_requirements",
    }
    assert expected <= set(data.__all__)
    for name in expected:
        assert hasattr(data, name), f"openlia.data missing {name!r}"


def test_deferred_subpackages_importable() -> None:
    for mod in (
        "openlia.data.review",
        "openlia.data.dispatch",
        "openlia.data.python_providers",
        "openlia.data.sentiment",
    ):
        m = importlib.import_module(mod)
        assert getattr(m, "__deferred__", False) is True


def test_catalog_module_active() -> None:
    """Catalog is no longer deferred — exposes build_catalog + ProviderCatalog."""
    from openlia.data import catalog

    assert getattr(catalog, "__deferred__", False) is False
    assert callable(catalog.build_catalog)
    assert hasattr(catalog, "ProviderCatalog")
    assert hasattr(catalog, "CatalogEntry")
