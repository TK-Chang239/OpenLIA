"""Tests for the parsed-template → TemplateSpec compiler (PR 13)."""

from __future__ import annotations

from openlia.reports.frameworks.template_spec import TemplateSpec
from openlia_server.services.template_compile import compile_template_spec
from openlia_server.services.template_parser import parse_template


def test_minimal_markdown_compiles_into_valid_template_spec() -> None:
    md = "Preamble line.\n\n# One\nbrief one\n\n# Two\nbrief two\n"
    spec = compile_template_spec(parse_template(md), name="t")

    # Round-trip through the runtime schema to assert shape compatibility.
    parsed = TemplateSpec.model_validate(spec)
    assert parsed.name == "t"
    assert parsed.global_preface == "Preamble line."
    assert [s.id for s in parsed.body_sections] == ["one", "two"]
    assert parsed.body_sections[0].brief == "brief one"
    assert parsed.synthesis_sections == ()


def test_document_frontmatter_overrides_name_and_optional_fields() -> None:
    md = (
        "<!-- openlia\n"
        "name: framework_v2\n"
        "freshness_budgets:\n"
        "  current_price: 7\n"
        "cover_bindings:\n"
        "  consensus_rating: analyst_consensus_rating\n"
        "-->\n\n"
        "# Section\nbody\n"
    )
    spec = compile_template_spec(parse_template(md), name="fallback")
    assert spec["name"] == "framework_v2"
    assert spec["freshness_budgets"] == {"current_price": 7}
    assert spec["cover_bindings"] == {"consensus_rating": "analyst_consensus_rating"}


def test_section_frontmatter_threads_voice_and_helpers() -> None:
    md = (
        "# Scorecard\n"
        "<!-- openlia\n"
        "voice: third_person_only\n"
        "word_target: 800\n"
        "preload_helpers:\n"
        "  - peer_multiple_implied_range\n"
        "lazy_helpers:\n"
        "  - historical_pe_band\n"
        "required_facts:\n"
        "  - segment_revenue_latest\n"
        "-->\n"
        "brief prose\n"
    )
    spec = compile_template_spec(parse_template(md), name="t")
    section = spec["body_sections"][0]
    assert section["voice"] == "third_person_only"
    assert section["word_target"] == 800
    assert section["eager_helpers"] == ("peer_multiple_implied_range",)
    assert section["lazy_helpers"] == ("historical_pe_band",)
    assert section["required_facts"] == ("segment_revenue_latest",)

    # Runtime schema accepts the compiled section.
    parsed = TemplateSpec.model_validate(spec)
    assert parsed.body_sections[0].voice == "third_person_only"


def test_synthesis_tier_routing_via_frontmatter() -> None:
    md = (
        "# Body\nbody brief\n\n"
        "# Synthesis\n<!-- openlia\ndispatch_tier: synthesis\n-->\nsyn brief\n"
    )
    spec = compile_template_spec(parse_template(md), name="t")
    assert [s["id"] for s in spec["body_sections"]] == ["body"]
    assert [s["id"] for s in spec["synthesis_sections"]] == ["synthesis"]


def test_meta_tier_routing_marks_dispatch_tier() -> None:
    md = "# Body\nbody\n\n# Self Audit\n<!-- openlia\ndispatch_tier: meta\n-->\naudit prose\n"
    spec = compile_template_spec(parse_template(md), name="t")
    audit = next(s for s in spec["synthesis_sections"] if s["id"] == "self_audit")
    assert audit["dispatch_tier"] == "meta"
    parsed = TemplateSpec.model_validate(spec)
    assert any(s.dispatch_tier == "meta" for s in parsed.synthesis_sections)
    assert len(parsed.meta_sections) == 1
