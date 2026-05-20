from __future__ import annotations

from openlia.llm.runtime.report_v2.packer.parser import (
    ParsedSection,
    TextSegment,
)
from openlia.llm.runtime.report_v2.packer.validator import (
    ValidationFinding,
    advocacy_language,
    cross_section_numeric_consistency,
    fetched_but_unused,
    quantitative_claim_near_citation,
    tombstone_regex,
    validate_section,
    word_count_minimum,
)


def _text(s: str, citation_ids: list[int] | None = None) -> TextSegment:
    return TextSegment(text=s, citation_ids=citation_ids or [])


def _parsed(segments: list) -> ParsedSection:
    return ParsedSection(
        frontmatter={"section_id": "x", "title": "X", "sources_used": [], "word_count_target": 600},
        segments=list(segments),
    )


def test_word_count_minimum_passes_at_or_above_70pct() -> None:
    parsed = _parsed([_text(" ".join(["word"] * 420))])
    findings = word_count_minimum(parsed, target=600)
    assert findings == []


def test_word_count_minimum_flags_below_70pct() -> None:
    parsed = _parsed([_text(" ".join(["word"] * 300))])
    findings = word_count_minimum(parsed, target=600)
    assert len(findings) == 1
    assert findings[0].check == "word_count_minimum"
    assert "300" in findings[0].detail


def test_word_count_minimum_counts_cjk_chars_individually() -> None:
    # Traditional Chinese prose with no inter-character whitespace.
    # ``.split()`` would return 1 "word"; the counter should count each
    # CJK ideograph as one unit.
    chinese_prose = "公" * 420
    parsed = _parsed([_text(chinese_prose)])
    findings = word_count_minimum(parsed, target=600)
    assert findings == []


def test_word_count_minimum_mixed_cjk_latin() -> None:
    # ``EBITDA`` plus 419 CJK chars → 420 units total → passes 70% of 600.
    parsed = _parsed([_text("EBITDA " + "公" * 419)])
    findings = word_count_minimum(parsed, target=600)
    assert findings == []


def test_tombstone_regex_flags_no_data_available() -> None:
    parsed = _parsed([_text("The data is great but No Data Available for the rest.")])
    findings = tombstone_regex(parsed)
    assert len(findings) == 1
    assert findings[0].check == "tombstone_regex"


def test_tombstone_regex_silent_when_clean() -> None:
    parsed = _parsed([_text("All metrics shown above are sourced.")])
    findings = tombstone_regex(parsed)
    assert findings == []


def test_quantitative_claim_near_citation_flags_uncited_number() -> None:
    parsed = _parsed([_text("Revenue grew 23% in fiscal 2024.")])
    findings = quantitative_claim_near_citation(parsed)
    assert any(f.check == "quantitative_claim_near_citation" for f in findings)


def test_quantitative_claim_near_citation_silent_when_cited() -> None:
    parsed = _parsed([_text("Revenue grew 23% in fiscal 2024 [3].", citation_ids=[3])])
    findings = quantitative_claim_near_citation(parsed)
    assert findings == []


def test_fetched_but_unused_flags_facts_never_referenced_in_prose_or_blocks() -> None:
    parsed = _parsed([_text("The company exists.")])
    findings = fetched_but_unused(
        parsed,
        facts_slice={"market_cap": object(), "revenue_cagr_3y": object()},
    )
    names = {f.detail.split(":")[1].strip() for f in findings}
    assert {"market_cap", "revenue_cagr_3y"}.issubset(names)


def test_fetched_but_unused_passes_when_fact_in_prose() -> None:
    parsed = _parsed([_text("The market cap is large.")])
    findings = fetched_but_unused(
        parsed,
        facts_slice={"market_cap": object()},
    )
    assert findings == []


def test_cross_section_numeric_consistency_flags_mismatched_claims() -> None:
    sec_a = _parsed([_text("Revenue CAGR 3y of 23.4% over the period [1].", citation_ids=[1])])
    sec_a.frontmatter["section_id"] = "financial_analysis"
    sec_b = _parsed(
        [_text("Revenue CAGR 3y of 24.7% across the projection [1].", citation_ids=[1])]
    )
    sec_b.frontmatter["section_id"] = "valuation_analysis"

    findings = cross_section_numeric_consistency([sec_a, sec_b])
    assert any(f.check == "cross_section_numeric_consistency" for f in findings)


def test_cross_section_numeric_consistency_silent_when_values_agree() -> None:
    sec_a = _parsed([_text("Revenue CAGR 3y of 23.4% over the period [1].", citation_ids=[1])])
    sec_a.frontmatter["section_id"] = "financial_analysis"
    sec_b = _parsed([_text("Revenue CAGR 3y of 23.4% in our model [1].", citation_ids=[1])])
    sec_b.frontmatter["section_id"] = "valuation_analysis"

    findings = cross_section_numeric_consistency([sec_a, sec_b])
    assert findings == []


def test_validate_section_runs_all_five_checks() -> None:
    parsed = _parsed([_text("Tiny.")])
    findings = validate_section(parsed, facts_slice={}, target_word_count=600)
    checks = {f.check for f in findings}
    assert "word_count_minimum" in checks


def test_validation_finding_default_severity_is_error() -> None:
    f = ValidationFinding(check="word_count_minimum", section_id="x", detail="too short")
    assert f.severity == "error"


def test_fetched_but_unused_severity_is_warning() -> None:
    parsed = _parsed([_text("The company exists.")])
    findings = fetched_but_unused(parsed, facts_slice={"market_cap": object()})
    assert all(f.severity == "warning" for f in findings)


# ---------------------------------------------------------------------------
# no-advocacy policy: first-person advocacy flagged; cited third-person
# attribution NOT flagged.
# ---------------------------------------------------------------------------


def test_advocacy_flags_we_recommend() -> None:
    parsed = _parsed([_text("We recommend BUY on Salesforce because of strong fundamentals.")])
    findings = advocacy_language(parsed)
    assert any(f.check == "advocacy_language" for f in findings)


def test_advocacy_flags_our_rating() -> None:
    parsed = _parsed([_text("Our rating is Hold pending clarity on the upgrade cycle.")])
    findings = advocacy_language(parsed)
    assert len(findings) == 1


def test_advocacy_flags_our_price_target() -> None:
    parsed = _parsed([_text("Our price target of $245 implies 18% upside.")])
    findings = advocacy_language(parsed)
    assert len(findings) == 1


def test_advocacy_flags_we_view_this_as() -> None:
    parsed = _parsed([_text("We view this as an attractive entry point.")])
    findings = advocacy_language(parsed)
    assert len(findings) == 1


def test_advocacy_flags_investment_thesis_unattributed() -> None:
    parsed = _parsed([_text("The investment thesis rests on platform expansion.")])
    findings = advocacy_language(parsed)
    assert len(findings) == 1


def test_advocacy_does_not_flag_cited_third_person_rating() -> None:
    """`JPMorgan rates Buy [c12]` is a report of source data, not advocacy."""
    parsed = _parsed([_text("JPMorgan rates Buy with a $300 target [c12].")])
    findings = advocacy_language(parsed)
    assert findings == []


def test_advocacy_does_not_flag_consensus_reflects() -> None:
    parsed = _parsed([_text("Consensus reflects a Hold with mean target $245 [c1].")])
    findings = advocacy_language(parsed)
    assert findings == []


def test_advocacy_does_not_flag_management_thesis() -> None:
    """`Investment thesis as described by management` is reportage, not advocacy."""
    parsed = _parsed([_text("Investment thesis as described by management centers on AI [c4].")])
    findings = advocacy_language(parsed)
    assert findings == []


def test_advocacy_check_runs_in_validate_section() -> None:
    parsed = _parsed([_text("We initiate at BUY.")])
    findings = validate_section(parsed, facts_slice={}, target_word_count=10)
    assert any(f.check == "advocacy_language" for f in findings)
