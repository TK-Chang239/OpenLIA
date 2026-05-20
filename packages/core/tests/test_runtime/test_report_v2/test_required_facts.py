"""Tests for the required_facts gate (PR 15)."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.required_facts import missing_required_facts
from openlia.reports.frameworks.template_spec import SectionSpec


def _section(*, required: tuple[str, ...] = ()) -> SectionSpec:
    return SectionSpec(
        id="s1",
        title="S1",
        brief="brief",
        required_facts=required,
    )


def test_no_required_facts_returns_empty_tuple() -> None:
    section = _section()
    assert missing_required_facts(section, ["any", "fact"]) == ()


def test_all_required_present_returns_empty_tuple() -> None:
    section = _section(required=("revenue_ttm", "shares_outstanding"))
    assert missing_required_facts(section, ["shares_outstanding", "revenue_ttm", "extra"]) == ()


def test_partial_present_returns_only_missing() -> None:
    section = _section(required=("a", "b", "c"))
    assert missing_required_facts(section, ["b"]) == ("a", "c")


def test_returns_in_declaration_order() -> None:
    section = _section(required=("zzz", "aaa", "mmm"))
    assert missing_required_facts(section, []) == ("zzz", "aaa", "mmm")
