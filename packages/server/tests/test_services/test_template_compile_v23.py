"""Tests for the v2.3 template compile service."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.templates import TemplateSpec
from openlia_server.services.template_compile_v23 import compile_v23_spec
from openlia_server.services.template_parser import parse_template


def test_compiles_simple_markdown_into_valid_template_spec():
    markdown = """\
# Overview
What the company does.

# Financials
Multi-period trajectory.

# Recommendation
Final stance.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="My initiation")
    # Validates as a real TemplateSpec — the core schema is the contract
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.name == "My initiation"
    assert [s.id for s in spec.sections] == ["overview", "financials", "recommendation"]
    assert [s.title for s in spec.sections] == ["Overview", "Financials", "Recommendation"]
    # Each section's intent should be the brief (with a fallback when brief is empty)
    assert spec.sections[0].intent.startswith("What the company does")


def test_uses_document_frontmatter_name_when_present():
    markdown = """\
<!-- openlia
name: My custom template
-->
# Only section
Body text.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="UNUSED")
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.name == "My custom template"


def test_reads_ticker_anchored_from_document_frontmatter():
    markdown = """\
<!-- openlia
name: Sector primer
ticker_anchored: false
-->
# Industry primer
Set up the sector.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="UNUSED")
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.ticker_anchored is False


def test_reads_default_length_from_document_frontmatter():
    markdown = """\
<!-- openlia
name: Brief
default_length: concise
-->
# Quick read
Short.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="UNUSED")
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.default_length == "concise"


def test_uses_shape_description_from_document_frontmatter():
    markdown = """\
<!-- openlia
name: Custom
shape_description: A custom sector-level note focused on lithium supply.
-->
# Primer
Body.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="UNUSED")
    spec = TemplateSpec.model_validate(spec_dict)
    assert "lithium supply" in spec.shape_description


def test_falls_back_to_template_name_in_shape_description_when_unset():
    markdown = """\
# Section
Body.
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="Fallback name")
    spec = TemplateSpec.model_validate(spec_dict)
    # Shape description must be non-empty (TemplateSpec requires min_length=1)
    assert spec.shape_description
    # Use the fallback name when no description is provided
    assert "Fallback name" in spec.shape_description


def test_reads_section_methodology_hints_from_frontmatter():
    markdown = """\
# Valuation
Present the DCF.

<!-- openlia
methodology_hints:
  - dcf
  - comps
-->
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="X")
    spec = TemplateSpec.model_validate(spec_dict)
    assert spec.sections[0].methodology_hints == ["dcf", "comps"]


def test_section_intent_falls_back_when_brief_is_empty():
    markdown = """\
# Section with no body
"""
    parsed = parse_template(markdown)
    spec_dict = compile_v23_spec(parsed, fallback_name="X")
    spec = TemplateSpec.model_validate(spec_dict)
    # SectionSpec.intent requires min_length=1
    assert spec.sections[0].intent
    # Sensible fallback — at least the section title shows up
    assert "Section with no body" in spec.sections[0].intent


def test_rejects_markdown_with_no_sections():
    """If the markdown has no H1/H2 headings, parse_template returns
    sections=(). compile_v23_spec must raise — TemplateSpec requires
    min_length=1 on sections."""
    markdown = "Just a paragraph, no headings."
    parsed = parse_template(markdown)
    with pytest.raises(ValueError, match="at least one section"):
        compile_v23_spec(parsed, fallback_name="X")
