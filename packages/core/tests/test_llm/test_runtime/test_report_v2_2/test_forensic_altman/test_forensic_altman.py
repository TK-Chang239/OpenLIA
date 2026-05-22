"""Tests for PR 2.6: Altman Z variants, Beneish M-score, dividend safety, integrity bundle.

Covers:
  - Registration of all 4 helpers
  - Altman Z: known-input / known-output for all 4 variants
  - Dividend safety: payout > 80% warning trigger
  - Beneish M-score: manipulator-like inputs produce M > -1.78
  - Statement integrity bundle: composition, composite score, skill doc
"""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------

FORENSIC_HELPERS = [
    "altman_z_variants",
    "beneish_m_score",
    "dividend_safety_panel",
    "statement_integrity_bundle",
]


@pytest.mark.parametrize("name", FORENSIC_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


@pytest.mark.parametrize("name", FORENSIC_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    arts = helper.schema.contract.produces_artifacts
    assert len(arts) >= 1


def test_statement_integrity_bundle_has_skill_doc() -> None:
    helper = get_helper("statement_integrity_bundle")
    assert helper is not None
    assert helper.schema.skill_doc is not None
    assert helper.schema.skill_doc.path == "skills/statement_integrity_bundle.md"
    assert helper.schema.skill_doc.estimated_tokens >= 1500


# ---------------------------------------------------------------------------
# Altman Z (original 1968)
# ---------------------------------------------------------------------------

# Textbook-style inputs producing a safe-zone score.
# Using approximate Altman 1968 verification:
#   Z = 1.2*(WC/TA) + 1.4*(RE/TA) + 3.3*(EBIT/TA) + 0.6*(MVE/TL) + 1.0*(S/TA)
# With TA=1000, WC=200, RE=400, EBIT=150, MVE=3000, TL=500, S=900:
#   = 1.2*0.20 + 1.4*0.40 + 3.3*0.15 + 0.6*6.00 + 1.0*0.90
#   = 0.24 + 0.56 + 0.495 + 3.60 + 0.90 = 5.795
_SAFE_INPUTS = dict(
    total_assets=1000.0,
    working_capital=200.0,
    retained_earnings=400.0,
    ebit=150.0,
    market_value_equity=3000.0,
    book_value_equity=500.0,
    book_value_total_liabilities=500.0,
    sales=900.0,
)


def test_altman_z_safe_zone() -> None:
    result = get_helper("altman_z_variants").impl(
        variant="z",
        **_SAFE_INPUTS,
    )
    assert result["classification"] == "safe"
    assert result["z_score"] > 2.99
    expected = (
        1.2 * 0.20 + 1.4 * 0.40 + 3.3 * 0.15 + 0.6 * (3000.0 / 500.0) + 1.0 * (900.0 / 1000.0)
    )
    assert result["z_score"] == pytest.approx(expected, abs=1e-3)


def test_altman_z_distress_zone() -> None:
    """Inputs designed to produce Z < 1.81."""
    result = get_helper("altman_z_variants").impl(
        working_capital=-50.0,
        retained_earnings=-200.0,
        ebit=-30.0,
        market_value_equity=50.0,
        book_value_equity=100.0,
        book_value_total_liabilities=800.0,
        sales=300.0,
        total_assets=900.0,
        variant="z",
    )
    assert result["classification"] == "distress"
    assert result["z_score"] < 1.81


def test_altman_z_gray_zone() -> None:
    """Inputs designed to produce 1.81 <= Z <= 2.99.

    With ta=1000, wc=50, re=100, ebit=50, mve=800, tl=400, s=600:
      Z = 1.2*0.05 + 1.4*0.10 + 3.3*0.05 + 0.6*2.0 + 1.0*0.60
        = 0.06 + 0.14 + 0.165 + 1.20 + 0.60 = 2.165  (gray zone)
    """
    result = get_helper("altman_z_variants").impl(
        working_capital=50.0,
        retained_earnings=100.0,
        ebit=50.0,
        market_value_equity=800.0,
        book_value_equity=300.0,
        book_value_total_liabilities=400.0,
        sales=600.0,
        total_assets=1000.0,
        variant="z",
    )
    assert result["classification"] == "gray"
    assert 1.81 <= result["z_score"] <= 2.99


# ---------------------------------------------------------------------------
# Altman Z' (private firms, BVE substitution verified)
# ---------------------------------------------------------------------------


def test_altman_z_prime_uses_book_equity() -> None:
    """Z' uses BVE/TL, not MVE/TL. Weight is 0.420 (not 0.6)."""
    bve = 600.0
    tl = 400.0
    ta = 1000.0
    result = get_helper("altman_z_variants").impl(
        working_capital=100.0,
        retained_earnings=300.0,
        ebit=120.0,
        book_value_equity=bve,
        book_value_total_liabilities=tl,
        sales=800.0,
        total_assets=ta,
        variant="z_prime",
        market_value_equity=None,
    )
    components = result["components"]
    # equity_to_liabilities = BVE / TL = 600/400 = 1.50
    assert components["equity_to_liabilities"]["value"] == pytest.approx(bve / tl, abs=1e-4)
    # weight for Z' equity term is 0.420
    assert components["equity_to_liabilities"]["weight"] == pytest.approx(0.420, abs=1e-6)
    # Verify contribution = weight * value
    assert components["equity_to_liabilities"]["contribution"] == pytest.approx(
        0.420 * (bve / tl), abs=1e-4
    )


def test_altman_z_prime_no_market_equity_needed() -> None:
    """Z' succeeds without market_value_equity."""
    result = get_helper("altman_z_variants").impl(
        working_capital=150.0,
        retained_earnings=250.0,
        ebit=100.0,
        book_value_equity=400.0,
        book_value_total_liabilities=500.0,
        sales=700.0,
        total_assets=1000.0,
        variant="z_prime",
    )
    assert "z_score" in result
    assert result["classification"] in ("safe", "gray", "distress")


# ---------------------------------------------------------------------------
# Altman Z" (non-manufacturing, 4 factors only — no Sales/TA)
# ---------------------------------------------------------------------------


def test_altman_z_double_prime_four_factors_only() -> None:
    """Z" has exactly 4 factors; no sales_to_ta component."""
    result = get_helper("altman_z_variants").impl(
        working_capital=200.0,
        retained_earnings=300.0,
        ebit=100.0,
        book_value_equity=400.0,
        book_value_total_liabilities=500.0,
        sales=None,
        total_assets=1000.0,
        variant="z_double_prime",
    )
    components = result["components"]
    assert "sales_to_ta" not in components
    assert set(components.keys()) == {
        "working_capital_to_ta",
        "retained_earnings_to_ta",
        "ebit_to_ta",
        "equity_to_liabilities",
    }


def test_altman_z_double_prime_formula() -> None:
    """Verify Z" = 6.56*WC/TA + 3.26*RE/TA + 6.72*EBIT/TA + 1.05*BVE/TL."""
    wc, re, ebit, bve, tl, ta = 200.0, 300.0, 100.0, 400.0, 500.0, 1000.0
    expected = 6.56 * (wc / ta) + 3.26 * (re / ta) + 6.72 * (ebit / ta) + 1.05 * (bve / tl)
    result = get_helper("altman_z_variants").impl(
        working_capital=wc,
        retained_earnings=re,
        ebit=ebit,
        book_value_equity=bve,
        book_value_total_liabilities=tl,
        sales=None,
        total_assets=ta,
        variant="z_double_prime",
    )
    assert result["z_score"] == pytest.approx(expected, abs=1e-3)


# ---------------------------------------------------------------------------
# EM Z" (emerging markets, +3.25 constant verified)
# ---------------------------------------------------------------------------


def test_em_z_double_prime_constant_offset() -> None:
    """EM Z" = Z" + 3.25. Both variants with same inputs should differ by 3.25."""
    common = dict(
        working_capital=100.0,
        retained_earnings=200.0,
        ebit=80.0,
        book_value_equity=300.0,
        book_value_total_liabilities=400.0,
        sales=None,
        total_assets=800.0,
    )
    z_dp = get_helper("altman_z_variants").impl(variant="z_double_prime", **common)
    em_z_dp = get_helper("altman_z_variants").impl(variant="em_z_double_prime", **common)

    assert em_z_dp["z_score"] == pytest.approx(z_dp["z_score"] + 3.25, abs=1e-4)


def test_em_z_double_prime_thresholds() -> None:
    """EM Z" thresholds are 4.35 (distress) and 5.85 (safe)."""
    result = get_helper("altman_z_variants").impl(
        working_capital=100.0,
        retained_earnings=200.0,
        ebit=80.0,
        book_value_equity=300.0,
        book_value_total_liabilities=400.0,
        sales=None,
        total_assets=800.0,
        variant="em_z_double_prime",
    )
    assert result["thresholds_used"] == {"distress": 4.35, "gray_upper": 5.85}


# ---------------------------------------------------------------------------
# Altman "all" variant
# ---------------------------------------------------------------------------


def test_altman_all_variant() -> None:
    """variant='all' returns a list of 4 variant results."""
    result = get_helper("altman_z_variants").impl(
        working_capital=200.0,
        retained_earnings=300.0,
        ebit=100.0,
        market_value_equity=2000.0,
        book_value_equity=400.0,
        book_value_total_liabilities=500.0,
        sales=800.0,
        total_assets=1000.0,
        variant="all",
    )
    assert "variants" in result
    assert len(result["variants"]) == 4
    variant_names = {v["variant_used"] for v in result["variants"]}
    assert variant_names == {"z", "z_prime", "z_double_prime", "em_z_double_prime"}


def test_altman_numeric_reconciliation() -> None:
    """sum(contribution_i) = z_score for variant Z."""
    result = get_helper("altman_z_variants").impl(
        working_capital=200.0,
        retained_earnings=400.0,
        ebit=150.0,
        market_value_equity=3000.0,
        book_value_equity=500.0,
        book_value_total_liabilities=500.0,
        sales=900.0,
        total_assets=1000.0,
        variant="z",
    )
    total_contribution = sum(c["contribution"] for c in result["components"].values())
    assert total_contribution == pytest.approx(result["z_score"], abs=1e-3)


# ---------------------------------------------------------------------------
# Dividend safety panel
# ---------------------------------------------------------------------------


def test_dividend_safety_payout_over_80_triggers_warning() -> None:
    """Payout > 80% (0.80) of NI triggers a warning per supplement §9."""
    # NI = 100, dividends per share = 0.90, shares = 100 -> total div = 90 -> payout = 90%
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=[50.0, 55.0, 60.0, 65.0, 70.0, 80.0, 90.0],
        net_income_series=[100.0, 105.0, 110.0, 115.0, 120.0, 115.0, 100.0],
        free_cash_flow_series=[80.0, 85.0, 90.0, 95.0, 100.0, 95.0, 85.0],
        ebitda_series=[150.0, 155.0, 160.0, 165.0, 170.0, 165.0, 150.0],
        interest_expense_series=[10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0],
        current_dividend_annualized=0.90,
        current_shares_outstanding=100.0,
        current_price=20.0,
    )
    # Payout of NI = 90 / 100 = 0.90 → should trigger warning
    assert result["current_payout_ratios"]["of_net_income"] == pytest.approx(0.90, abs=1e-4)
    warning_text = " ".join(result["warnings"])
    assert "80%" in warning_text or "0.80" in warning_text or "Payout" in warning_text


def test_dividend_safety_fcf_coverage_warning() -> None:
    """FCF coverage < 1.2x triggers a warning."""
    # total_div = 1.10 * 100 = 110, FCF = 120 -> coverage = 120/110 = 1.09 < 1.2
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=[80.0, 90.0, 100.0, 110.0],
        net_income_series=[150.0, 155.0, 160.0, 150.0],
        free_cash_flow_series=[120.0, 125.0, 130.0, 120.0],
        ebitda_series=[200.0, 205.0, 210.0, 200.0],
        interest_expense_series=[10.0, 10.0, 10.0, 10.0],
        current_dividend_annualized=1.10,
        current_shares_outstanding=100.0,
        current_price=30.0,
    )
    assert result["coverage_ratios"]["fcf_to_dividends"] == pytest.approx(120.0 / 110.0, abs=1e-3)
    assert result["coverage_ratios"]["fcf_to_dividends"] < 1.2
    warning_text = " ".join(result["warnings"])
    assert "1.2" in warning_text or "coverage" in warning_text.lower()


def test_dividend_safety_safe_classification() -> None:
    """Long streak, low payout -> safe classification."""
    annual_divs = [1.0, 1.05, 1.10, 1.15, 1.20, 1.25, 1.30, 1.35, 1.40, 1.50, 1.55]
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=annual_divs,
        net_income_series=[5.0] * 11,
        free_cash_flow_series=[4.5] * 11,
        ebitda_series=[8.0] * 11,
        interest_expense_series=[0.5] * 11,
        current_dividend_annualized=1.55,
        current_shares_outstanding=1.0,
        current_price=40.0,
    )
    # payout of NI = 1.55 / 5.0 = 0.31 (well below 0.70)
    assert result["current_payout_ratios"]["of_net_income"] == pytest.approx(1.55 / 5.0, abs=1e-4)
    assert result["classification"] == "safe"


def test_dividend_safety_distressed_payout_over_100() -> None:
    """Payout > 1.0 -> distressed classification."""
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=[2.0, 2.0, 2.0],
        net_income_series=[1.5, 1.5, 1.5],
        free_cash_flow_series=[1.0, 1.0, 1.0],
        ebitda_series=[3.0, 3.0, 3.0],
        interest_expense_series=[0.5, 0.5, 0.5],
        current_dividend_annualized=2.0,
        current_shares_outstanding=1.0,
        current_price=10.0,
    )
    # payout of NI = 2.0 / 1.5 = 1.33 > 1.00
    assert result["current_payout_ratios"]["of_net_income"] > 1.0
    assert result["classification"] == "distressed"


def test_dividend_safety_stress_verdict_bands() -> None:
    """Stress test with -25% shock; verify verdict band logic."""
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=[3.0, 3.0, 3.0],
        net_income_series=[6.0, 6.0, 6.0],
        free_cash_flow_series=[5.5, 5.5, 5.5],
        ebitda_series=[9.0, 9.0, 9.0],
        interest_expense_series=[0.5, 0.5, 0.5],
        current_dividend_annualized=3.0,
        current_shares_outstanding=1.0,
        current_price=50.0,
        stress_scenario_pct=-0.25,
    )
    # Stressed NI = 6.0 * 0.75 = 4.5; stressed payout = 3.0/4.5 = 0.667 < 0.70
    assert result["stress_test"]["implied_stressed_ni_payout"] == pytest.approx(3.0 / 4.5, abs=1e-4)
    assert result["stress_test"]["verdict_at_shock"] == "covered_with_buffer"


def test_dividend_safety_yield_computed() -> None:
    result = get_helper("dividend_safety_panel").impl(
        annual_dividends=[2.0],
        net_income_series=[10.0],
        free_cash_flow_series=[8.0],
        ebitda_series=[15.0],
        interest_expense_series=[1.0],
        current_dividend_annualized=2.0,
        current_shares_outstanding=100.0,
        current_price=40.0,
    )
    assert result["current_yield"] == pytest.approx(2.0 / 40.0, abs=1e-6)


# ---------------------------------------------------------------------------
# Beneish M-score
# ---------------------------------------------------------------------------


def _clean_inputs() -> dict:
    """Inputs that should yield M-score well below -1.78 (no manipulation signal)."""
    return dict(
        accounts_receivable_t=100.0,
        accounts_receivable_t1=95.0,
        revenue_t=1000.0,
        revenue_t1=950.0,
        gross_profit_t=400.0,
        gross_profit_t1=380.0,
        current_assets_t=300.0,
        current_assets_t1=280.0,
        ppe_t=500.0,
        ppe_t1=480.0,
        total_assets_t=1200.0,
        total_assets_t1=1100.0,
        depreciation_t=60.0,
        depreciation_t1=55.0,
        sga_t=100.0,
        sga_t1=95.0,
        total_debt_t=200.0,
        total_debt_t1=210.0,
        net_income_t=150.0,
        cfo_t=145.0,  # NI ≈ CFO -> low TATA
    )


def test_beneish_clean_company_no_signal() -> None:
    result = get_helper("beneish_m_score").impl(**_clean_inputs())
    assert result["classification"] == "no_signal"
    assert result["m_score"] < -1.78


def test_beneish_manipulator_signal() -> None:
    """Enron-like inflated values: high DSRI, poor GMI, high TATA, high LVGI."""
    result = get_helper("beneish_m_score").impl(
        # AR grows much faster than revenue (DSRI > 1)
        accounts_receivable_t=250.0,
        accounts_receivable_t1=100.0,
        revenue_t=1000.0,
        revenue_t1=900.0,
        # Margin deteriorates (GMI > 1 = prior > current)
        gross_profit_t=200.0,
        gross_profit_t1=270.0,
        # AQI: fewer current/PPE assets -> more "soft" assets
        current_assets_t=200.0,
        current_assets_t1=300.0,
        ppe_t=200.0,
        ppe_t1=300.0,
        total_assets_t=1500.0,
        total_assets_t1=1200.0,
        # Depreciation slowing relative to PPE (DEPI > 1)
        depreciation_t=40.0,
        depreciation_t1=60.0,
        # SGA growing fast (SGAI > 1)
        sga_t=220.0,
        sga_t1=160.0,
        # Leverage increasing (LVGI > 1)
        total_debt_t=600.0,
        total_debt_t1=400.0,
        # Very high accruals: NI >> CFO (high TATA)
        net_income_t=200.0,
        cfo_t=20.0,  # large NI - CFO gap
    )
    assert result["classification"] == "likely_manipulator"
    assert result["m_score"] > -1.78


def test_beneish_known_coefficients() -> None:
    """Manually compute M-score from known inputs and verify match."""
    inputs = _clean_inputs()
    result = get_helper("beneish_m_score").impl(**inputs)

    ar_t, ar_t1 = inputs["accounts_receivable_t"], inputs["accounts_receivable_t1"]
    rev_t, rev_t1 = inputs["revenue_t"], inputs["revenue_t1"]
    gp_t, gp_t1 = inputs["gross_profit_t"], inputs["gross_profit_t1"]
    ca_t, ca_t1 = inputs["current_assets_t"], inputs["current_assets_t1"]
    ppe_t, ppe_t1 = inputs["ppe_t"], inputs["ppe_t1"]
    ta_t, ta_t1 = inputs["total_assets_t"], inputs["total_assets_t1"]
    dep_t, dep_t1 = inputs["depreciation_t"], inputs["depreciation_t1"]
    sga_t, sga_t1 = inputs["sga_t"], inputs["sga_t1"]
    debt_t, debt_t1 = inputs["total_debt_t"], inputs["total_debt_t1"]
    ni_t = inputs["net_income_t"]
    cfo_t = inputs["cfo_t"]

    dsri = (ar_t / rev_t) / (ar_t1 / rev_t1)
    gmi = (gp_t1 / rev_t1) / (gp_t / rev_t)
    aqi = (1 - (ca_t + ppe_t) / ta_t) / (1 - (ca_t1 + ppe_t1) / ta_t1)
    sgi = rev_t / rev_t1
    depi = (dep_t1 / (dep_t1 + ppe_t1)) / (dep_t / (dep_t + ppe_t))
    sgai = (sga_t / rev_t) / (sga_t1 / rev_t1)
    lvgi = (debt_t / ta_t) / (debt_t1 / ta_t1)
    tata = (ni_t - cfo_t) / ta_t

    m_expected = (
        -4.84
        + 0.92 * dsri
        + 0.528 * gmi
        + 0.404 * aqi
        + 0.892 * sgi
        + 0.115 * depi
        - 0.172 * sgai
        + 4.679 * tata
        - 0.327 * lvgi
    )
    assert result["m_score"] == pytest.approx(m_expected, abs=1e-3)


def test_beneish_all_8_components_present() -> None:
    result = get_helper("beneish_m_score").impl(**_clean_inputs())
    assert set(result["components"].keys()) == {
        "DSRI",
        "GMI",
        "AQI",
        "SGI",
        "DEPI",
        "SGAI",
        "LVGI",
        "TATA",
    }


def test_beneish_threshold_in_output() -> None:
    result = get_helper("beneish_m_score").impl(**_clean_inputs())
    assert result["threshold"] == -1.78


# ---------------------------------------------------------------------------
# Statement integrity bundle
# ---------------------------------------------------------------------------


def test_statement_integrity_bundle_composes_4_sub_panels() -> None:
    altman_out = {
        "variant_used": "z_double_prime",
        "z_score": 3.5,
        "classification": "safe",
        "thresholds_used": {"distress": 1.10, "gray_upper": 2.60},
        "components": {},
        "warnings": [],
    }
    beneish_out = {
        "m_score": -2.5,
        "threshold": -1.78,
        "classification": "no_signal",
        "verdict": "no manipulation signal",
        "components": {},
        "weighted_contributions": {},
        "top_drivers": [],
        "warnings": ["TATA uses NI - CFO proxy"],
    }
    cross_out = {
        "checks": [
            {"name": "accounting_equation", "passed": True},
            {"name": "ni_to_re", "passed": True},
        ],
        "warnings": [],
    }
    oti_out = {
        "pct_of_net_income": 3.0,  # < 5%, low concern
        "warnings": [],
    }

    result = get_helper("statement_integrity_bundle").impl(
        altman_z_output=altman_out,
        beneish_m_output=beneish_out,
        cross_statement_output=cross_out,
        one_time_item_output=oti_out,
    )

    assert "composite_statement_integrity_score" in result
    assert "classification" in result
    assert "component_scores" in result
    assert set(result["component_scores"].keys()) == {
        "altman_z",
        "beneish",
        "cross_statement",
        "one_time_items",
    }
    assert 0 <= result["composite_statement_integrity_score"] <= 100


def test_statement_integrity_bundle_all_none_is_neutral() -> None:
    """All None inputs -> each component 50 -> composite = 50."""
    result = get_helper("statement_integrity_bundle").impl()
    assert result["composite_statement_integrity_score"] == pytest.approx(50.0, abs=1e-4)
    assert result["classification"] == "moderate_integrity"


def test_statement_integrity_bundle_high_integrity() -> None:
    altman_out = {
        "z_score": 4.5,
        "classification": "safe",
        "components": {},
        "thresholds_used": {"distress": 1.10, "gray_upper": 2.60},
        "warnings": [],
    }
    beneish_out = {
        "m_score": -3.0,
        "classification": "no_signal",
        "components": {},
        "weighted_contributions": {},
        "top_drivers": [],
        "warnings": [],
    }
    cross_out = {
        "checks": [{"name": "check1", "passed": True}],
        "warnings": [],
    }
    oti_out = {
        "pct_of_net_income": 1.0,
        "warnings": [],
    }
    result = get_helper("statement_integrity_bundle").impl(
        altman_z_output=altman_out,
        beneish_m_output=beneish_out,
        cross_statement_output=cross_out,
        one_time_item_output=oti_out,
    )
    # altman=90, beneish=85, cross=90, oti=90
    # composite = 0.25*90 + 0.30*85 + 0.25*90 + 0.20*90 = 22.5+25.5+22.5+18 = 88.5
    assert result["composite_statement_integrity_score"] == pytest.approx(88.5, abs=0.5)
    assert result["classification"] == "high_integrity"


def test_statement_integrity_bundle_low_integrity() -> None:
    """Distress + manipulator + 2 cross-stmt flags + high OTI -> low_integrity."""
    altman_out = {
        "z_score": 0.8,
        "classification": "distress",
        "components": {},
        "thresholds_used": {"distress": 1.10, "gray_upper": 2.60},
        "warnings": [],
    }
    beneish_out = {
        "m_score": -1.0,
        "classification": "likely_manipulator",
        "components": {},
        "weighted_contributions": {},
        "top_drivers": [],
        "warnings": [],
    }
    cross_out = {
        "checks": [
            {"name": "check1", "passed": False},
            {"name": "check2", "passed": False},
        ],
        "warnings": [],
    }
    oti_out = {
        "pct_of_net_income": 35.0,  # > 20%
        "warnings": [],
    }
    result = get_helper("statement_integrity_bundle").impl(
        altman_z_output=altman_out,
        beneish_m_output=beneish_out,
        cross_statement_output=cross_out,
        one_time_item_output=oti_out,
    )
    # altman=15, beneish=15, cross=30, oti=30
    # composite = 0.25*15 + 0.30*15 + 0.25*30 + 0.20*30 = 3.75+4.5+7.5+6 = 21.75
    assert result["composite_statement_integrity_score"] == pytest.approx(21.75, abs=0.5)
    assert result["classification"] == "low_integrity"
    assert len(result["top_concerns"]) >= 2


def test_statement_integrity_bundle_skill_doc_path() -> None:
    helper = get_helper("statement_integrity_bundle")
    assert helper.schema.skill_doc.path == "skills/statement_integrity_bundle.md"


def test_statement_integrity_skill_doc_file_exists() -> None:
    """Verify the skill doc file is present on disk."""
    from openlia.llm.runtime.report_v2_2.tools import library_helpers

    skill_path = (
        Path(library_helpers.__file__).parent / "skills" / "statement_integrity_bundle.md"
    )
    assert skill_path.exists(), f"Skill doc not found at {skill_path}"
    content = skill_path.read_text()
    assert "statement_integrity_bundle" in content
    assert "Beneish" in content
    assert "Altman" in content
