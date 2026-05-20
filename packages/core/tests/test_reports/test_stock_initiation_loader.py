"""Tests for the default stock_initiation template loader.

In PR 1 the loader re-exports the existing runner constants — section list,
briefs, style guide, system role — without moving them. PR 2 will move the
content into the loader; for now this test verifies the loader produces a
TemplateSpec whose contents match the still-hardcoded runner values, locking
the contract before any code migrates.
"""

from __future__ import annotations


def test_loader_returns_template_spec_with_expected_name() -> None:
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    assert spec.name == "stock_initiation"


def test_loader_body_section_ids_match_runner_constant() -> None:
    from openlia.llm.runtime.report_v2.runner import BODY_SECTIONS_STOCK_INITIATION
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    assert tuple(s.id for s in spec.body_sections) == BODY_SECTIONS_STOCK_INITIATION


def test_loader_synthesis_section_ids_match_runner_constant() -> None:
    from openlia.llm.runtime.report_v2.runner import SYNTHESIS_SECTIONS_STOCK_INITIATION
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    assert tuple(s.id for s in spec.synthesis_sections) == SYNTHESIS_SECTIONS_STOCK_INITIATION


def test_loader_section_briefs_match_runner_constant() -> None:
    from openlia.llm.runtime.report_v2.runner import DEFAULT_BRIEFS
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    for section in (*spec.body_sections, *spec.synthesis_sections):
        assert section.brief == DEFAULT_BRIEFS[section.id], (
            f"section {section.id!r} brief diverges from runner constant"
        )


def test_loader_word_targets_match_runner_constant() -> None:
    from openlia.llm.runtime.report_v2.runner import DEFAULT_WORD_TARGETS
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    assert spec.default_word_targets == DEFAULT_WORD_TARGETS


def test_loader_carries_system_role_and_style_guide_strings() -> None:
    from openlia.reports.frameworks.loaders.stock_initiation import load_stock_initiation_template

    spec = load_stock_initiation_template()

    assert "equity research" in spec.system_role.lower()
    assert "information-aggregation" in spec.style_guide.lower()


def test_default_registry_pre_registers_stock_initiation() -> None:
    # Importing the loader module triggers registration.
    import openlia.reports.frameworks.loaders.stock_initiation  # noqa: F401
    from openlia.reports.frameworks.registry import default_registry

    spec = default_registry.get("stock_initiation")

    assert spec.name == "stock_initiation"
