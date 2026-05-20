"""Tests for the numeric reconciliation validator (WS4 / P7).

Regression tests reproduce the historical NVDA / CRM / WOLF failures from
the reviewer's notes. Positive tests confirm clean sections pass and
near-match-within-tolerance passes. The retry-hook test confirms the
section-level feedback rendering produces an actionable retry prompt.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.types import Fact
from openlia.llm.runtime.report_v2.validators.numeric_consistency import (
    NumericValidationError,
    build_section_retry_prompt,
    extract_numbers,
    validate_sections,
)


def _fact(name: str, value: object, source_ids: list[int] | None = None) -> Fact:
    return Fact(
        name=name,
        value=value,
        source_ids=source_ids or [1],
        extractor="deterministic",
    )


# ---------------------------------------------------------------------------
# Extractor unit tests
# ---------------------------------------------------------------------------


class TestExtractNumbers:
    def test_currency_scaled(self) -> None:
        out = extract_numbers("Revenue was $215.9B in FY2026.")
        # Year "2026" should not be extracted; only the dollar figure.
        kinds = [n.kind for n in out]
        assert "currency_scaled" in kinds
        currency = next(n for n in out if n.kind == "currency_scaled")
        assert currency.value == pytest.approx(215_900_000_000)

    def test_percent(self) -> None:
        out = extract_numbers("Operating margin of 60.4%.")
        assert len(out) == 1
        assert out[0].kind == "percent"
        assert out[0].value == pytest.approx(0.604)

    def test_basis_points(self) -> None:
        out = extract_numbers("Margin compressed 250bps.")
        assert len(out) == 1
        assert out[0].kind == "basis_points"
        assert out[0].value == pytest.approx(0.025)

    def test_ratio(self) -> None:
        out = extract_numbers("Trading at 38.2x forward earnings.")
        assert len(out) == 1
        assert out[0].kind == "ratio"
        assert out[0].value == pytest.approx(38.2)

    def test_currency_plain(self) -> None:
        out = extract_numbers("Share price closed at $173.")
        assert any(n.kind == "currency_plain" and n.value == 173 for n in out)

    def test_year_not_extracted(self) -> None:
        out = extract_numbers("Founded in 2009; revenue grew through 2024.")
        # No $/%/x markers on the years — they should not be extracted as
        # quantitative figures.
        assert out == []


# ---------------------------------------------------------------------------
# Year-label consistency
# ---------------------------------------------------------------------------


class TestYearLabelConsistency:
    def test_year_in_revenue_years_passes(self) -> None:
        facts = {
            "revenue_years": _fact("revenue_years", [2022, 2023, 2024, 2025, 2026]),
            "fiscal_year_end_latest": _fact("fiscal_year_end_latest", "2026-01-26"),
        }
        report = validate_sections({"company_overview": "Revenue grew across FY2024."}, facts)
        year_failures = [f for f in report.failures if f.failure_type == "year_label_mismatch"]
        assert year_failures == []

    def test_year_outside_revenue_years_fails(self) -> None:
        # CRM/WOLF FY label slipped by one year.
        facts = {
            "revenue_years": _fact("revenue_years", [2022, 2023, 2024, 2025, 2026]),
            "fiscal_year_end_latest": _fact("fiscal_year_end_latest", "2026-01-26"),
        }
        report = validate_sections(
            {"valuation_analysis": "Forecast for FY2025 implies $X."},
            # No FY2025 in revenue_years (revenue ends 2026)
            facts,
        )
        # NOTE: 2025 is actually in revenue_years above; let me explicitly
        # check the slip year.
        report = validate_sections(
            {"valuation_analysis": "Forecast for FY2027 implies $X."},
            facts,
        )
        year_failures = [f for f in report.failures if f.failure_type == "year_label_mismatch"]
        assert len(year_failures) == 1
        assert year_failures[0].offending_text == "FY2027"


# ---------------------------------------------------------------------------
# Numeric ↔ fact equality
# ---------------------------------------------------------------------------


class TestNumericEquality:
    def test_within_tolerance_passes(self) -> None:
        facts = {
            "operating_margin_ttm": _fact("operating_margin_ttm", 0.604),
        }
        report = validate_sections(
            {"financial_analysis": "Operating margin 60.4%."},
            facts,
        )
        # operating margin 60.4% matches operating_margin_ttm = 0.604 exactly.
        not_in = [f for f in report.failures if f.failure_type == "numeric_not_in_facts"]
        assert not_in == []

    def test_near_match_within_tolerance_passes(self) -> None:
        facts = {
            "revenue_ttm": _fact("revenue_ttm", 100_000_000_000),
        }
        # $100.5B is within 1% of $100B
        report = validate_sections(
            {"company_overview": "Revenue $100.5B"},
            facts,
        )
        not_in = [f for f in report.failures if f.failure_type == "numeric_not_in_facts"]
        assert not_in == []

    def test_outside_tolerance_fails(self) -> None:
        # NVDA's "65.0% TTM operating margin" prose vs operating_margin_ttm = 0.604
        facts = {
            "operating_margin_ttm": _fact("operating_margin_ttm", 0.604),
            # Provide a small set of other facts so derivation can't
            # accidentally produce 0.65 from a ratio.
            "shares_outstanding": _fact("shares_outstanding", 24_500_000_000),
        }
        report = validate_sections(
            {"financial_analysis": "Reported a 65.0% TTM operating margin in the latest period."},
            facts,
        )
        not_in_or_identity = [
            f
            for f in report.failures
            if f.failure_type in {"numeric_not_in_facts", "identity_equation_violation"}
        ]
        assert len(not_in_or_identity) >= 1


# ---------------------------------------------------------------------------
# Arithmetic spot-checks
# ---------------------------------------------------------------------------


class TestArithmetic:
    def test_peg_disagreement_fails(self) -> None:
        # NVDA: "PEG of 0.68x" but pe_ratio_forward / (growth * 100)
        # = 45.5 / (1.00 * 100) = 0.455
        facts = {
            "pe_ratio_forward": _fact("pe_ratio_forward", 45.5),
            "consensus_eps_growth_fy_next": _fact("consensus_eps_growth_fy_next", 1.00),
        }
        report = validate_sections(
            {"valuation_analysis": "Trades at a PEG of 0.68x against forward growth."},
            facts,
        )
        ari = [f for f in report.failures if f.failure_type == "arithmetic_disagreement"]
        assert len(ari) == 1
        assert ari[0].expected_value == pytest.approx(0.455)
        assert ari[0].actual_value == pytest.approx(0.68)

    def test_peg_agreement_passes(self) -> None:
        # PEG 0.455 is correct given the same facts.
        facts = {
            "pe_ratio_forward": _fact("pe_ratio_forward", 45.5),
            "consensus_eps_growth_fy_next": _fact("consensus_eps_growth_fy_next", 1.00),
        }
        report = validate_sections(
            {"valuation_analysis": "PEG of 0.455 reflects forward growth."},
            facts,
        )
        ari = [f for f in report.failures if f.failure_type == "arithmetic_disagreement"]
        assert ari == []

    def test_margin_spread_disagreement_fails(self) -> None:
        facts = {
            "gross_margin_ttm": _fact("gross_margin_ttm", 0.75),
            "operating_margin_ttm": _fact("operating_margin_ttm", 0.60),
        }
        # Cited 12 percentage points; actual is 15.
        report = validate_sections(
            {"financial_analysis": "Gross-to-operating margin spread of 12 percentage points."},
            facts,
        )
        ari = [f for f in report.failures if f.failure_type == "arithmetic_disagreement"]
        assert len(ari) == 1


# ---------------------------------------------------------------------------
# Cross-section identity equations
# ---------------------------------------------------------------------------


class TestIdentityEquations:
    def test_market_cap_identity_passes(self) -> None:
        facts = {
            "current_price": _fact("current_price", 100.0),
            "shares_outstanding": _fact("shares_outstanding", 1_000_000_000),
            "market_cap": _fact("market_cap", 100_000_000_000),
        }
        report = validate_sections({}, facts)
        id_fails = [f for f in report.failures if f.failure_type == "identity_equation_violation"]
        assert id_fails == []
        assert any("market_cap" in s for s in report.identity_equations_checked)

    def test_market_cap_identity_fails(self) -> None:
        facts = {
            "current_price": _fact("current_price", 100.0),
            "shares_outstanding": _fact("shares_outstanding", 1_000_000_000),
            "market_cap": _fact("market_cap", 150_000_000_000),  # 50% off
        }
        report = validate_sections({}, facts)
        id_fails = [f for f in report.failures if f.failure_type == "identity_equation_violation"]
        assert any(f.fact_name == "market_cap" for f in id_fails)

    def test_crm_upside_equation_fails(self) -> None:
        # CRM: $330 target at "+32%" with current_price=$173. Actual upside
        # is (330-173)/173 ≈ 0.908 = ~91%, not 32%.
        facts = {
            "current_price": _fact("current_price", 173.0),
            "consensus_target_mean": _fact("consensus_target_mean", 330.0),
            "consensus_upside_pct": _fact("consensus_upside_pct", 0.32),
        }
        report = validate_sections({}, facts)
        id_fails = [
            f
            for f in report.failures
            if f.failure_type == "identity_equation_violation"
            and f.fact_name == "consensus_upside_pct"
        ]
        assert len(id_fails) == 1

    def test_wolf_hold_with_negative_upside_passes(self) -> None:
        # Hold rating with -9% upside is acceptable (no rating-coherence rule
        # against Hold + negative).
        facts = {
            "current_price": _fact("current_price", 24.0),
            "consensus_target_mean": _fact("consensus_target_mean", 21.84),
            "consensus_upside_pct": _fact("consensus_upside_pct", -0.09),
            "consensus_rating": _fact("consensus_rating", "Hold"),
        }
        report = validate_sections({}, facts)
        coherence_fails = [
            f
            for f in report.failures
            if f.failure_type == "identity_equation_violation"
            and "rating" in f.detail.lower()
            and "upside" in f.detail.lower()
        ]
        assert coherence_fails == []

    def test_buy_with_negative_upside_fails(self) -> None:
        # Same numbers but rating = Buy now triggers the coherence rule.
        facts = {
            "current_price": _fact("current_price", 24.0),
            "consensus_target_mean": _fact("consensus_target_mean", 21.84),
            "consensus_upside_pct": _fact("consensus_upside_pct", -0.09),
            "consensus_rating": _fact("consensus_rating", "Buy"),
        }
        report = validate_sections({}, facts)
        coherence_fails = [
            f
            for f in report.failures
            if f.failure_type == "identity_equation_violation"
            and "rating" in f.detail.lower()
            and "negative" in f.detail.lower()
        ]
        assert len(coherence_fails) == 1

    def test_consensus_facts_dict_overrides(self) -> None:
        # consensus_facts dict can supply values not present as Facts.
        facts = {"current_price": _fact("current_price", 100.0)}
        consensus = {
            "consensus_target_mean": 200.0,
            "consensus_upside_pct": 0.40,  # claimed 40%; actual is 100%
        }
        report = validate_sections({}, facts, consensus_facts=consensus)
        id_fails = [
            f
            for f in report.failures
            if f.failure_type == "identity_equation_violation"
            and f.fact_name == "consensus_upside_pct"
        ]
        assert len(id_fails) == 1

    def test_operating_margin_prose_disagreement_fails(self) -> None:
        # NVDA: prose says "65% operating margin" but fact says 60.4%.
        facts = {"operating_margin_ttm": _fact("operating_margin_ttm", 0.604)}
        report = validate_sections(
            {"financial_analysis": "Maintained a robust operating margin of 65.0%."},
            facts,
        )
        # Should produce an identity-equation violation on the operating
        # margin prose.
        margin_fails = [
            f
            for f in report.failures
            if f.failure_type == "identity_equation_violation"
            and f.fact_name == "operating_margin_ttm"
        ]
        assert len(margin_fails) >= 1


# ---------------------------------------------------------------------------
# First-person voice + tombstones
# ---------------------------------------------------------------------------


class TestFirstPersonVoice:
    def test_first_person_in_analyst_view_fails(self) -> None:
        report = validate_sections(
            {"analyst_view": ("We believe NVDA is undervalued. Our base case is $250.")},
            {},
        )
        fp = [f for f in report.failures if f.failure_type == "first_person_voice"]
        assert len(fp) >= 1

    def test_first_person_in_other_section_passes(self) -> None:
        # First-person is only blocked in analyst_view / investment_recommendation.
        report = validate_sections(
            {"recent_developments": "We believe these moves matter."},
            {},
        )
        fp = [f for f in report.failures if f.failure_type == "first_person_voice"]
        assert fp == []

    def test_third_person_passes(self) -> None:
        report = validate_sections(
            {"analyst_view": ("Consensus reflects a Buy rating with a mean target of $250.")},
            {},
        )
        fp = [f for f in report.failures if f.failure_type == "first_person_voice"]
        assert fp == []


class TestTombstones:
    def test_tombstone_phrase_fails(self) -> None:
        report = validate_sections(
            {"valuation_analysis": ("This is not a single target-setting exercise; see context.")},
            {},
        )
        tomb = [f for f in report.failures if f.failure_type == "tombstone_phrase"]
        assert len(tomb) == 1


# ---------------------------------------------------------------------------
# Report-level behaviour
# ---------------------------------------------------------------------------


class TestReportBehavior:
    def test_passed_property(self) -> None:
        report = validate_sections(
            {"company_overview": "NVIDIA is a semi designer."},
            {},
        )
        assert report.passed

    def test_hard_vs_soft_failures(self) -> None:
        # Identity equation = hard; numeric_not_in_facts = soft.
        facts = {
            "current_price": _fact("current_price", 100.0),
            "shares_outstanding": _fact("shares_outstanding", 1_000_000_000),
            "market_cap": _fact("market_cap", 150_000_000_000),
            "revenue_ttm": _fact("revenue_ttm", 100_000_000_000),
        }
        report = validate_sections(
            {"company_overview": "Revenue grew to $999B last year."},
            facts,
        )
        assert any(f.failure_type == "identity_equation_violation" for f in report.failures)
        assert len(report.hard_failures) >= 1
        # Numeric mismatch on $999B should appear as soft.
        assert any(f.failure_type == "numeric_not_in_facts" for f in report.soft_failures)

    def test_numeric_validation_error_carries_failures(self) -> None:
        facts = {
            "current_price": _fact("current_price", 100.0),
            "shares_outstanding": _fact("shares_outstanding", 1_000_000_000),
            "market_cap": _fact("market_cap", 150_000_000_000),
        }
        report = validate_sections({}, facts)
        with pytest.raises(NumericValidationError) as exc_info:
            raise NumericValidationError(report.hard_failures)
        assert exc_info.value.failures
        assert "market_cap" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Per-section retry hook
# ---------------------------------------------------------------------------


class TestRetryHook:
    def test_retry_prompt_appends_failures(self) -> None:
        facts = {
            "revenue_ttm": _fact("revenue_ttm", 100_000_000_000),
        }
        first_report = validate_sections(
            {"company_overview": "Revenue was $999B last year."},
            facts,
        )
        soft = first_report.soft_failures
        assert any(f.failure_type == "numeric_not_in_facts" for f in soft)

        base_prompt = "BASE PROMPT"
        retry_prompt = build_section_retry_prompt(base_prompt, soft)
        assert "BASE PROMPT" in retry_prompt
        assert "FAILED NUMERIC RECONCILIATION" in retry_prompt
        assert "999" in retry_prompt or "numeric_not_in_facts" in retry_prompt

    def test_retry_resolves_on_correct_value(self) -> None:
        # Simulate the runner's single retry: if the section is re-emitted
        # with the corrected number, the validator should now pass.
        facts = {
            "revenue_ttm": _fact("revenue_ttm", 100_000_000_000),
        }
        # First attempt: wrong number.
        first = validate_sections({"company_overview": "Revenue was $999B last year."}, facts)
        assert any(f.failure_type == "numeric_not_in_facts" for f in first.failures)

        # Retry: correct number. Validator should now find no
        # numeric_not_in_facts failure.
        second = validate_sections({"company_overview": "Revenue was $100B last year."}, facts)
        not_in = [f for f in second.failures if f.failure_type == "numeric_not_in_facts"]
        assert not_in == []
