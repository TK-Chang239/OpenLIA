"""Unit tests for the deterministic UNCITED_NUMBER check.

The check runs in VERIFY's _deterministic_checks. Pre-VERIFY, the WRITE
mint step has already converted DERIVE/ESTIMATE markers into CITE
markers, so any digit-bearing token outside an exempt set is a real
fabrication and must route the section back to WRITE.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_3.schemas import (
    IssueKind,
    IssueSeverity,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages.verify import _check_uncited_numbers


def _ws(body: str, section_id: str = "s1") -> WrittenSection:
    return WrittenSection(section_id=section_id, title="T", body=body)


def test_passes_when_body_has_no_digits():
    issues = _check_uncited_numbers([_ws("Plain prose with no numbers at all.")])
    assert issues == []


def test_passes_when_every_number_is_inside_a_cite_marker():
    issues = _check_uncited_numbers(
        [_ws("Revenue {{CITE:rev_ttm}} grew {{CITE:rev_growth_yoy}} YoY.")]
    )
    assert issues == []


def test_passes_when_number_is_inside_a_fig_marker():
    issues = _check_uncited_numbers([_ws("See {{FIG:chart_3}} for the trend.")])
    assert issues == []


def test_flags_naked_dollar_amount_in_prose():
    issues = _check_uncited_numbers([_ws("Revenue of $60.9B last quarter.")])
    assert len(issues) == 1
    assert issues[0].kind == IssueKind.UNCITED_NUMBER
    assert issues[0].severity == IssueSeverity.HIGH
    assert "$60.9B" in issues[0].detail


def test_flags_naked_percentage_in_prose():
    issues = _check_uncited_numbers([_ws("Margins expanded 200 basis points.")])
    assert len(issues) == 1
    assert issues[0].kind == IssueKind.UNCITED_NUMBER


def test_flags_naked_multiple_token():
    issues = _check_uncited_numbers([_ws("Trades at 15x forward earnings.")])
    assert len(issues) == 1


def test_exempts_four_digit_year_alone():
    issues = _check_uncited_numbers([_ws("In 2025 the company restructured.")])
    assert issues == []


def test_exempts_fiscal_year_token():
    issues = _check_uncited_numbers([_ws("FY2025 results pending.")])
    assert issues == []


def test_exempts_ordinal_suffix():
    issues = _check_uncited_numbers(
        [_ws("Ranked 3rd in the segment and 12th overall.")]
    )
    assert issues == []


def test_exempts_quarter_token():
    issues = _check_uncited_numbers([_ws("Q3 results beat consensus.")])
    assert issues == []


def test_flags_naked_number_alongside_cited_one():
    issues = _check_uncited_numbers(
        [_ws("Revenue {{CITE:rev_ttm}} but margins fell to 18.5%.")]
    )
    assert len(issues) == 1
    assert "18.5" in issues[0].detail


def test_carries_section_id_through_to_issue():
    issues = _check_uncited_numbers(
        [_ws("Trades at 15x earnings.", section_id="valuation")]
    )
    assert issues[0].section_id == "valuation"


def test_reports_only_first_violation_per_section():
    """A section with three naked numbers reports one issue listing
    all of them — not three separate issues — to keep the rewrite
    prompt focused."""
    issues = _check_uncited_numbers(
        [_ws("Revenue $60B, margin 25%, trading at 12x.")]
    )
    assert len(issues) == 1
    detail = issues[0].detail
    assert "$60B" in detail
    assert "25%" in detail
    assert "12x" in detail


def test_flags_body_leading_naked_number():
    """A body that starts with a bare numeric token must be flagged.
    Exercises the start>=1 / start>=2 guards in _is_exempt — those
    must not silently exempt a leading number."""
    issues = _check_uncited_numbers([_ws("15x forward earnings is the multiple.")])
    assert len(issues) == 1
    assert "15x" in issues[0].detail


def test_flags_negative_number_with_full_token_in_detail():
    """A negative number must be flagged AND the detail message must
    include the minus sign so the rewrite prompt sees the actual token
    the writer typed."""
    issues = _check_uncited_numbers([_ws("Margins compressed -25% YoY.")])
    assert len(issues) == 1
    assert "-25%" in issues[0].detail
