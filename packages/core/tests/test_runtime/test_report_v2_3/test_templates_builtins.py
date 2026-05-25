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


def test_builtin_template_ids_are_unique():
    ids = [t.template_id for t in BUILTIN_TEMPLATES.values()]
    assert len(ids) == len(set(ids))


def test_sector_research_builtin_is_not_ticker_anchored():
    """Sector-level reports do not require a subject ticker — the
    'sector' IS the subject. Flipped in Phase 3 to demonstrate the
    ticker_anchored flag end-to-end."""
    from openlia.llm.runtime.report_v2_3.schemas import ReportType
    from openlia.llm.runtime.report_v2_3.templates import get_builtin

    t = get_builtin(ReportType.SECTOR_RESEARCH)
    assert t.ticker_anchored is False


def test_other_builtins_remain_ticker_anchored():
    """INITIATION and UPDATE stay ticker-anchored — they are inherently
    single-name. Only SECTOR_RESEARCH is thematic."""
    from openlia.llm.runtime.report_v2_3.schemas import ReportType
    from openlia.llm.runtime.report_v2_3.templates import get_builtin

    for rt in (ReportType.INITIATION, ReportType.UPDATE):
        assert get_builtin(rt).ticker_anchored is True


def test_builtin_names_match_v2_2_mode_labels():
    """The pill renders built-ins as flat siblings of user uploads. The
    three default names must mirror the v2.2 mode labels so the user
    sees consistent terminology across engines."""
    assert get_builtin(ReportType.INITIATION).name == "Stock Initiation"
    assert get_builtin(ReportType.UPDATE).name == "Stock Update"
    assert get_builtin(ReportType.SECTOR_RESEARCH).name == "Sector Research"


def test_sector_research_shape_description_signals_no_specific_company():
    """The shape_description text should signal sector-level, not
    company-specific, so the clarifier prompt doesn't bias toward
    asking for a ticker."""
    from openlia.llm.runtime.report_v2_3.schemas import ReportType
    from openlia.llm.runtime.report_v2_3.templates import get_builtin

    desc = get_builtin(ReportType.SECTOR_RESEARCH).shape_description.lower()
    assert "sector" in desc
