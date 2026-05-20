"""Tests for the TemplateRegistry — maps template IDs to TemplateSpec loaders.

Loaders are deferred (called when `get` is invoked) so importing the registry
doesn't force loading every template's resources eagerly. The default
`stock_initiation` template ships pre-registered.
"""

from __future__ import annotations

import pytest


def test_registry_starts_empty_by_default() -> None:
    from openlia.reports.frameworks.registry import TemplateRegistry

    registry = TemplateRegistry()

    assert registry.list_template_ids() == ()


def test_register_and_get_returns_loaded_spec() -> None:
    from openlia.reports.frameworks.registry import TemplateRegistry
    from openlia.reports.frameworks.template_spec import TemplateSpec

    registry = TemplateRegistry()
    spec = TemplateSpec(name="x", global_preface="", body_sections=(), synthesis_sections=())
    registry.register("x", lambda: spec)

    assert registry.get("x") is spec


def test_get_raises_for_unknown_template_id() -> None:
    from openlia.reports.frameworks.registry import TemplateRegistry, UnknownTemplateError

    registry = TemplateRegistry()

    with pytest.raises(UnknownTemplateError, match="unknown_template"):
        registry.get("unknown_template")


def test_register_rejects_duplicate_template_id() -> None:
    from openlia.reports.frameworks.registry import TemplateRegistry
    from openlia.reports.frameworks.template_spec import TemplateSpec

    registry = TemplateRegistry()
    spec = TemplateSpec(name="x", global_preface="", body_sections=(), synthesis_sections=())
    registry.register("x", lambda: spec)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("x", lambda: spec)


def test_loader_called_lazily_on_first_get() -> None:
    from openlia.reports.frameworks.registry import TemplateRegistry
    from openlia.reports.frameworks.template_spec import TemplateSpec

    call_count = [0]

    def loader() -> TemplateSpec:
        call_count[0] += 1
        return TemplateSpec(name="x", global_preface="", body_sections=(), synthesis_sections=())

    registry = TemplateRegistry()
    registry.register("x", loader)
    assert call_count[0] == 0  # registration does not call loader

    registry.get("x")
    registry.get("x")
    assert call_count[0] == 2  # called each get; no caching at this layer
