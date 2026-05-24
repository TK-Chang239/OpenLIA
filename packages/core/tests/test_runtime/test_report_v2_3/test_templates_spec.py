"""Tests for the TemplateSpec / SectionSpec Pydantic schema."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportLength
from openlia.llm.runtime.report_v2_3.templates import SectionSpec, TemplateSpec
from pydantic import ValidationError


def _section(**overrides) -> SectionSpec:
    defaults = dict(
        id="overview",
        title="Overview",
        intent="Business overview anchored to the latest reported segment mix.",
    )
    defaults.update(overrides)
    return SectionSpec(**defaults)


def test_section_spec_requires_id_title_intent():
    s = _section()
    assert s.id == "overview"
    assert s.title == "Overview"
    assert s.intent.startswith("Business overview")
    assert s.methodology_hints == []


def test_section_spec_id_must_be_slug():
    with pytest.raises(ValidationError):
        _section(id="Not A Slug")


def test_section_spec_rejects_empty_intent():
    with pytest.raises(ValidationError):
        _section(intent="")


def test_template_spec_requires_at_least_one_section():
    with pytest.raises(ValidationError):
        TemplateSpec(
            template_id="empty",
            name="Empty",
            shape_description="No sections.",
            sections=[],
        )


def test_template_spec_section_ids_must_be_unique():
    with pytest.raises(ValidationError, match="duplicate"):
        TemplateSpec(
            template_id="dup_ids",
            name="Dup",
            shape_description="Two sections with the same id.",
            sections=[_section(id="x"), _section(id="x")],
        )


def test_template_spec_defaults():
    t = TemplateSpec(
        template_id="t1",
        name="T1",
        shape_description="One-section template.",
        sections=[_section()],
    )
    assert t.ticker_anchored is True
    assert t.default_length is None


def test_template_spec_accepts_default_length():
    t = TemplateSpec(
        template_id="t1",
        name="T1",
        shape_description="One-section template.",
        sections=[_section()],
        default_length=ReportLength.CONCISE,
    )
    assert t.default_length == ReportLength.CONCISE


def test_template_spec_round_trips_via_json():
    src = TemplateSpec(
        template_id="t1",
        name="T1",
        shape_description="Round-trip test.",
        sections=[_section(methodology_hints=["use DCF", "compare to peers"])],
        ticker_anchored=False,
    )
    dumped = src.model_dump_json()
    restored = TemplateSpec.model_validate_json(dumped)
    assert restored == src
