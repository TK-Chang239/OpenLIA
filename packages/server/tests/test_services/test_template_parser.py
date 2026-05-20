"""Tests for the mechanical template parser (PR 11)."""

from __future__ import annotations

from openlia_server.services.template_parser import (
    parse_template,
    slugify,
)


def test_slugify_lowercases_and_replaces_non_alphanumeric() -> None:
    assert slugify("Company Overview") == "company_overview"
    assert slugify("§16 Scorecard") == "16_scorecard"
    assert slugify("===") == "section"  # empty result fallback


def test_parse_returns_global_preface_before_first_heading() -> None:
    md = "Preamble text here.\n\n# First Section\nBody."

    out = parse_template(md)

    assert out.global_preface == "Preamble text here."
    assert len(out.sections) == 1


def test_parse_extracts_h1_and_h2_sections() -> None:
    md = """\
# A
body of A
## B
body of B
# C
body of C
"""

    out = parse_template(md)

    assert [s.id for s in out.sections] == ["a", "b", "c"]
    assert [s.title for s in out.sections] == ["A", "B", "C"]
    assert out.sections[0].brief == "body of A"
    assert out.sections[1].brief == "body of B"


def test_parse_disambiguates_duplicate_slugs_with_numeric_suffix() -> None:
    md = "# Risks\nbody1\n# Risks\nbody2\n"

    out = parse_template(md)

    assert [s.id for s in out.sections] == ["risks", "risks_2"]


def test_parse_extracts_section_frontmatter() -> None:
    md = """\
# Valuation

<!-- openlia
voice: third_person_only
preload_helpers:
  - peer_multiple_implied_range
  - historical_pe_band
-->

Section body prose.
"""

    out = parse_template(md)

    section = out.sections[0]
    assert section.frontmatter["voice"] == "third_person_only"
    assert section.frontmatter["preload_helpers"] == [
        "peer_multiple_implied_range",
        "historical_pe_band",
    ]
    assert section.brief == "Section body prose."


def test_parse_handles_missing_frontmatter_gracefully() -> None:
    md = "# X\nbody"

    out = parse_template(md)

    assert out.sections[0].frontmatter == {}


def test_parse_ignores_malformed_frontmatter() -> None:
    md = """\
# X
<!-- openlia
this: is: not: valid: yaml: here:
-->

body
"""

    out = parse_template(md)

    # Malformed YAML => frontmatter is {} and the block is stripped.
    assert out.sections[0].frontmatter == {}


def test_parse_extracts_document_level_frontmatter() -> None:
    md = """\
<!-- openlia
name: My Template
freshness_budgets:
  current_price: 14
-->

# First Section
body
"""

    out = parse_template(md)

    assert out.document_frontmatter["name"] == "My Template"
    assert out.document_frontmatter["freshness_budgets"] == {"current_price": 14}


def test_parse_empty_body_produces_no_sections() -> None:
    out = parse_template("")

    assert out.sections == ()
    assert out.global_preface == ""


def test_parse_handles_nested_h3_inside_h2_section() -> None:
    md = """\
# Top
intro paragraph
## Sub
subsection body

### H3 stays inside Sub
inner content
"""

    out = parse_template(md)

    # H3 is NOT a boundary — it stays inside the H2 section's brief
    assert [s.title for s in out.sections] == ["Top", "Sub"]
    assert "H3 stays inside Sub" in out.sections[1].brief
    assert "inner content" in out.sections[1].brief
