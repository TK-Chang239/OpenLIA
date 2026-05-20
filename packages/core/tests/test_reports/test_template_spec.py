"""Tests for the TemplateSpec dataclass — the per-template configuration container.

A TemplateSpec carries everything the runner needs to dispatch a report against
a specific report template: section list, briefs, style guide, optional declarative
fields. The default equity-research template is built as a Python loader; uploaded
user templates are constructed mechanically from parsed markdown.
"""

from __future__ import annotations

import pytest


def test_section_spec_constructs_with_required_fields() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec

    section = SectionSpec(
        id="company_overview",
        title="Company Overview",
        brief="Cover ticker, sector, headcount.",
    )

    assert section.id == "company_overview"
    assert section.title == "Company Overview"
    assert section.brief == "Cover ticker, sector, headcount."


def test_section_spec_optional_fields_default_to_universal_values() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec

    section = SectionSpec(id="x", title="X", brief="x")

    assert section.voice == "any"
    assert section.word_target is None
    assert section.dispatch_tier == "body"
    assert section.eager_helpers == ()
    assert section.lazy_helpers == ()
    assert section.required_facts == ()


def test_template_spec_constructs_with_required_fields() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    spec = TemplateSpec(
        name="stock_initiation",
        global_preface="",
        body_sections=(SectionSpec(id="a", title="A", brief="a"),),
        synthesis_sections=(SectionSpec(id="b", title="B", brief="b"),),
    )

    assert spec.name == "stock_initiation"
    assert spec.global_preface == ""
    assert len(spec.body_sections) == 1
    assert len(spec.synthesis_sections) == 1


def test_template_spec_optional_fields_default_safely() -> None:
    from openlia.reports.frameworks.template_spec import TemplateSpec

    spec = TemplateSpec(name="x", global_preface="", body_sections=(), synthesis_sections=())

    assert spec.style_guide == ""
    assert spec.system_role == "You are a research section writer."
    assert spec.default_word_targets == {}
    assert spec.freshness_budgets == {}
    assert spec.identity_equations == ()
    assert spec.material_event_classes == ()
    assert spec.catalyst_classes == ()
    assert spec.industry_modes == ()
    assert spec.cover_bindings == {}
    assert spec.web_search_budget_default == 10


def test_template_spec_section_by_id_returns_matching_section() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    sec = SectionSpec(id="valuation_analysis", title="Valuation Analysis", brief="...")
    spec = TemplateSpec(name="x", global_preface="", body_sections=(sec,), synthesis_sections=())

    assert spec.section_by_id("valuation_analysis") is sec


def test_template_spec_section_by_id_returns_none_when_missing() -> None:
    from openlia.reports.frameworks.template_spec import TemplateSpec

    spec = TemplateSpec(name="x", global_preface="", body_sections=(), synthesis_sections=())

    assert spec.section_by_id("nonexistent") is None


def test_template_spec_partition_invariant_rejects_helper_in_both_eager_and_lazy() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    bad_section = SectionSpec(
        id="x",
        title="X",
        brief="x",
        eager_helpers=("dcf_intrinsic_value",),
        lazy_helpers=("dcf_intrinsic_value",),
    )

    with pytest.raises(ValueError, match=r"eager.*lazy.*disjoint"):
        TemplateSpec(
            name="bad", global_preface="", body_sections=(bad_section,), synthesis_sections=()
        )
