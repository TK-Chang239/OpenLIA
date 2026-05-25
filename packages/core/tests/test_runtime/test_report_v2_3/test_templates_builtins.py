"""Every ReportType must have a registered built-in TemplateSpec."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates import (
    BUILTIN_TEMPLATES,
    TemplateSpec,
    get_builtin,
)


def test_every_report_type_has_a_builtin():
    for rt in ReportType:
        assert rt in BUILTIN_TEMPLATES, f"No built-in for {rt}"


def test_get_builtin_returns_a_template_spec():
    for rt in ReportType:
        t = get_builtin(rt)
        assert isinstance(t, TemplateSpec)
        assert len(t.sections) >= 1
        assert t.template_id.startswith(rt.value)


def test_get_builtin_raises_on_unknown_report_type():
    class FakeType:
        value = "nonexistent"

    with pytest.raises(KeyError):
        get_builtin(FakeType())  # type: ignore[arg-type]


def test_builtin_initiation_has_valuation_section():
    t = get_builtin(ReportType.INITIATION)
    section_ids = {s.id for s in t.sections}
    assert "valuation" in section_ids


def test_builtin_morning_brief_is_concise():
    t = get_builtin(ReportType.MORNING_BRIEF)
    assert len(t.sections) <= 3  # brief by name
    assert t.default_length is not None  # caller can rely on a default


def test_builtin_template_ids_are_unique():
    ids = [t.template_id for t in BUILTIN_TEMPLATES.values()]
    assert len(ids) == len(set(ids))
