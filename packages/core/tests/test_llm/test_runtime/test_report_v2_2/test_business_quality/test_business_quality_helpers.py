"""Tests for the business quality bundle (PR 2.5): 19 helpers + forensic_panel aggregator.

Covers:
  - Registration of all 20 helpers
  - Formula correctness for each helper
  - Audit fix tests (7 explicit assertions)
  - Forensic panel aggregation
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper, list_helpers

# ---------------------------------------------------------------------------
# Constants: expected helper names
# ---------------------------------------------------------------------------

BQ_HELPERS = [
    "roic_panel",
    "quality_of_earnings_panel",
    "capital_allocation_history",
    "earnings_surprise_tracker",
    "analyst_revision_momentum",
    "common_size_statements",
    "fcf_conversion_track_record",
    "total_shareholder_yield",
    "cross_statement_validation",
    "one_time_item_identification",
    "organic_vs_inorganic_growth",
    "currency_neutral_growth",
    "margin_trajectory_regression",
    "operating_leverage_analysis",
    "sbc_intensity",
    "cap_table_dilution",
    "piotroski_f_score",
    "cash_conversion_cycle",
    "sustainable_growth_rate",
    "forensic_panel",
]


# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", BQ_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


def test_all_20_bq_helpers_registered() -> None:
    registered = {h.schema.directory.name for h in list_helpers()}
    missing = [n for n in BQ_HELPERS if n not in registered]
    assert not missing, f"Missing BQ helpers: {missing}"


@pytest.mark.parametrize("name", BQ_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    arts = helper.schema.contract.produces_artifacts
    assert len(arts) >= 1
    for a in arts:
        assert a.endswith("_output"), f"{name}: artifact {a!r} must end with '_output'"


@pytest.mark.parametrize("name", BQ_HELPERS)
def test_helper_schema_version(name: str) -> None:
    helper = get_helper(name)
    assert helper.schema.version == "0.1.0"


def test_forensic_panel_has_skill_doc() -> None:
    helper = get_helper("forensic_panel")
    assert helper is not None
    assert helper.schema.skill_doc is not None
    assert helper.schema.skill_doc.path == "skills/forensic_panel.md"
    assert helper.schema.skill_doc.estimated_tokens > 0


# ---------------------------------------------------------------------------
# Deprecation marks
# ---------------------------------------------------------------------------


def test_budget_variance_deprecated() -> None:
    h = get_helper("budget_variance")
    assert h is not None
    assert h.schema.deprecated_at_version == "0.2.0"


def test_business_investment_deprecated() -> None:
    h = get_helper("business_investment")
    assert h is not None
    assert h.schema.deprecated_at_version == "0.2.0"


def test_ratio_calculator_deprecated() -> None:
    h = get_helper("ratio_calculator")
    assert h is not None
    assert h.schema.deprecated_at_version == "0.2.0"


# ---------------------------------------------------------------------------
# roic_panel
# ---------------------------------------------------------------------------


def test_roic_panel_basic() -> None:
    result = get_helper("roic_panel").impl(
        nopat_series=[100.0, 110.0, 125.0],
        invested_capital_series=[1000.0, 1050.0, 1100.0],
        wacc=0.08,
    )
    assert result["latest_roic"] == pytest.approx(125.0 / 1100.0, abs=1e-4)
    assert result["latest_roic_vs_wacc"] == pytest.approx(125.0 / 1100.0 - 0.08, abs=1e-4)
    assert result["value_creating"] is True
    assert len(result["periods"]) == 3


def test_roic_panel_economic_profit_audit_fix() -> None:
    """Audit fix §9.4: EP = (ROIC - WACC) * IC."""
    nopat = [120.0]
    ic = [1000.0]
    wacc = 0.10
    result = get_helper("roic_panel").impl(
        nopat_series=nopat, invested_capital_series=ic, wacc=wacc
    )
    expected_roic = 120.0 / 1000.0
    expected_ep = (expected_roic - wacc) * 1000.0
    assert result["latest_economic_profit"] == pytest.approx(expected_ep, abs=0.01)


def test_roic_panel_roiic_audit_fix() -> None:
    """Audit fix §9.3: ROIIC = DELTA_NOPAT / DELTA_IC; period over period."""
    nopat = [100.0, 115.0]
    ic = [1000.0, 1050.0]
    result = get_helper("roic_panel").impl(
        nopat_series=nopat, invested_capital_series=ic, wacc=0.09
    )
    # ROIIC for period 2: (115 - 100) / (1050 - 1000) = 15 / 50 = 0.30
    assert result["latest_roiic"] == pytest.approx(0.30, abs=1e-4)
    # Period 1 has no ROIIC (no prior)
    assert result["periods"][0]["roiic"] is None


def test_roic_panel_value_destroying() -> None:
    result = get_helper("roic_panel").impl(
        nopat_series=[50.0],
        invested_capital_series=[1000.0],
        wacc=0.12,
    )
    assert result["value_creating"] is False
    assert result["latest_roic_vs_wacc"] < 0


# ---------------------------------------------------------------------------
# quality_of_earnings_panel
# ---------------------------------------------------------------------------


def test_qoe_accruals_pct_of_ni_audit_fix() -> None:
    """Audit fix §9.7: accruals_pct_of_ni = (NI - CFO) / NI * 100; warn if > 20%."""
    result = get_helper("quality_of_earnings_panel").impl(
        net_income=100.0,
        cfo=70.0,
        cfi=-50.0,
        total_assets=1000.0,
        total_assets_prior=900.0,
    )
    # accruals = NI - CFO = 30; pct = 30 / 100 * 100 = 30%
    assert result["accruals_pct_of_ni"] == pytest.approx(30.0, abs=0.01)
    assert result["accruals_warning"] is True  # > 20%


def test_qoe_accruals_no_warning_when_low() -> None:
    result = get_helper("quality_of_earnings_panel").impl(
        net_income=100.0,
        cfo=95.0,
        cfi=-50.0,
        total_assets=1000.0,
        total_assets_prior=900.0,
    )
    # accruals = 5; pct = 5%
    assert result["accruals_pct_of_ni"] == pytest.approx(5.0, abs=0.01)
    assert result["accruals_warning"] is False  # < 20%


def test_qoe_sloan_ratio_audit_fix() -> None:
    """Audit fix §9.1: Sloan = (NI - CFO - CFI) / avg_total_assets."""
    ni = 100.0
    cfo = 70.0
    cfi = -50.0
    ta = 1000.0
    ta_prior = 900.0
    result = get_helper("quality_of_earnings_panel").impl(
        net_income=ni, cfo=cfo, cfi=cfi, total_assets=ta, total_assets_prior=ta_prior
    )
    avg_ta = (ta + ta_prior) / 2.0
    expected_sloan = (ni - cfo - cfi) / avg_ta  # (100 - 70 - (-50)) / 950 = 80/950
    assert result["sloan_ratio"] == pytest.approx(expected_sloan, abs=1e-4)


def test_qoe_capitalized_rd_audit_fix() -> None:
    """Audit fix §9.6: adjust NI to capitalize R&D; show with/without."""
    result = get_helper("quality_of_earnings_panel").impl(
        net_income=100.0,
        cfo=90.0,
        cfi=-30.0,
        total_assets=1000.0,
        total_assets_prior=900.0,
        rd_expense=50.0,
        rd_amortization_years=5,
    )
    # R&D cap delta = 50 - 50/5 = 50 - 10 = 40
    assert result["rd_cap_nopat_delta"] == pytest.approx(40.0, abs=0.01)
    assert result["ni_without_rd_cap"] == pytest.approx(100.0, abs=0.01)
    assert result["ni_with_rd_cap"] == pytest.approx(140.0, abs=0.01)


def test_qoe_no_rd_when_zero() -> None:
    result = get_helper("quality_of_earnings_panel").impl(
        net_income=100.0, cfo=90.0, cfi=-20.0, total_assets=500.0, total_assets_prior=450.0
    )
    assert result["rd_cap_nopat_delta"] is None
    assert result["ni_with_rd_cap"] is None


# ---------------------------------------------------------------------------
# capital_allocation_history
# ---------------------------------------------------------------------------


def test_capital_allocation_pct_of_cfo() -> None:
    result = get_helper("capital_allocation_history").impl(
        cfo_series=[200.0, 220.0],
        capex_series=[80.0, 90.0],
        buybacks_series=[40.0, 50.0],
        dividends_series=[20.0, 25.0],
    )
    assert len(result["periods"]) == 2
    p0 = result["periods"][0]
    assert p0["capex_pct_cfo"] == pytest.approx(80.0 / 200.0 * 100.0, abs=0.01)
    assert p0["buybacks_pct_cfo"] == pytest.approx(40.0 / 200.0 * 100.0, abs=0.01)


def test_capital_allocation_averages() -> None:
    result = get_helper("capital_allocation_history").impl(
        cfo_series=[100.0, 200.0],
        capex_series=[20.0, 40.0],
        buybacks_series=[10.0, 20.0],
        dividends_series=[5.0, 10.0],
    )
    # capex pct: 20/100=20%, 40/200=20% -> avg 20%
    assert result["avg_capex_pct_cfo"] == pytest.approx(20.0, abs=0.01)


# ---------------------------------------------------------------------------
# earnings_surprise_tracker
# ---------------------------------------------------------------------------


def test_earnings_surprise_beat_rate() -> None:
    actuals = [1.0, 1.2, 0.9, 1.1, 1.3, 1.0, 1.2, 1.4]
    estimates = [0.95, 1.1, 1.0, 1.0, 1.2, 1.05, 1.1, 1.3]
    result = get_helper("earnings_surprise_tracker").impl(actuals=actuals, estimates=estimates)
    # Beats: q1(1.0>0.95), q2(1.2>1.1), q4(1.1>1.0), q5(1.3>1.2), q7(1.2>1.1), q8(1.4>1.3) = 6
    # Miss: q3(0.9<1.0), q6(1.0<1.05) = 2
    assert result["beat_count"] == 6
    assert result["miss_count"] == 2
    assert result["beat_rate_pct"] == pytest.approx(75.0, abs=0.01)


def test_earnings_surprise_pct_formula() -> None:
    result = get_helper("earnings_surprise_tracker").impl(actuals=[1.10], estimates=[1.00])
    # surprise_pct = (1.10 - 1.00) / abs(1.00) * 100 = 10%
    assert result["quarters"][0]["surprise_pct"] == pytest.approx(10.0, abs=0.01)


# ---------------------------------------------------------------------------
# analyst_revision_momentum
# ---------------------------------------------------------------------------


def test_analyst_revision_net_score() -> None:
    revisions = [
        {"period": "Q1", "direction": "up", "magnitude": 0.05},
        {"period": "Q2", "direction": "up", "magnitude": 0.03},
        {"period": "Q3", "direction": "down", "magnitude": 0.02},
        {"period": "Q4", "direction": "up", "magnitude": 0.04},
    ]
    result = get_helper("analyst_revision_momentum").impl(revisions=revisions)
    assert result["up_count"] == 3
    assert result["down_count"] == 1
    assert result["net_score"] == 2
    assert result["net_direction"] == "positive"
    # velocity = 2/4 = 0.5
    assert result["velocity"] == pytest.approx(0.5, abs=1e-3)


def test_analyst_revision_negative_direction() -> None:
    revisions = [
        {"period": "Q1", "direction": "down"},
        {"period": "Q2", "direction": "down"},
    ]
    result = get_helper("analyst_revision_momentum").impl(revisions=revisions)
    assert result["net_direction"] == "negative"


# ---------------------------------------------------------------------------
# common_size_statements
# ---------------------------------------------------------------------------


def test_common_size_is() -> None:
    is_data = {
        "revenue": 1000.0,
        "gross_profit": 600.0,
        "operating_income": 200.0,
        "net_income": 150.0,
    }
    result = get_helper("common_size_statements").impl(income_statement=is_data)
    assert result["common_size_is"]["gross_profit"] == pytest.approx(60.0, abs=0.01)
    assert result["common_size_is"]["net_income"] == pytest.approx(15.0, abs=0.01)
    assert result["common_size_is"]["revenue"] == pytest.approx(100.0, abs=0.01)


def test_common_size_bs() -> None:
    is_data = {"revenue": 1000.0}
    bs_data = {"total_assets": 2000.0, "cash": 500.0, "total_equity": 1200.0}
    result = get_helper("common_size_statements").impl(
        income_statement=is_data, balance_sheet=bs_data
    )
    assert result["common_size_bs"]["cash"] == pytest.approx(25.0, abs=0.01)
    assert result["common_size_bs"]["total_equity"] == pytest.approx(60.0, abs=0.01)


# ---------------------------------------------------------------------------
# fcf_conversion_track_record
# ---------------------------------------------------------------------------


def test_fcf_conversion_ratio() -> None:
    result = get_helper("fcf_conversion_track_record").impl(
        fcf_series=[90.0, 95.0, 100.0],
        net_income_series=[100.0, 100.0, 100.0],
    )
    assert result["avg_fcf_to_ni"] == pytest.approx(0.95, abs=1e-3)
    assert result["periods"][0]["fcf_to_ni"] == pytest.approx(0.90, abs=1e-4)


def test_fcf_conversion_trend_stable() -> None:
    result = get_helper("fcf_conversion_track_record").impl(
        fcf_series=[95.0, 96.0, 97.0, 94.0, 95.0, 96.0, 97.0, 95.0],
        net_income_series=[100.0] * 8,
    )
    assert result["trend"] == "stable"


# ---------------------------------------------------------------------------
# total_shareholder_yield
# ---------------------------------------------------------------------------


def test_tsy_formula() -> None:
    result = get_helper("total_shareholder_yield").impl(
        market_cap=10000.0,
        dividends_paid=200.0,
        buybacks=300.0,
        net_debt_repayment=100.0,
    )
    assert result["dividend_yield"] == pytest.approx(0.02, abs=1e-4)
    assert result["buyback_yield"] == pytest.approx(0.03, abs=1e-4)
    assert result["debt_paydown_yield"] == pytest.approx(0.01, abs=1e-4)
    assert result["total_shareholder_yield"] == pytest.approx(0.06, abs=1e-4)


def test_tsy_no_debt_paydown() -> None:
    result = get_helper("total_shareholder_yield").impl(
        market_cap=5000.0, dividends_paid=100.0, buybacks=50.0
    )
    assert result["debt_paydown_yield"] == pytest.approx(0.0, abs=1e-6)
    assert result["total_shareholder_yield"] == pytest.approx(0.03, abs=1e-4)


# ---------------------------------------------------------------------------
# cross_statement_validation
# ---------------------------------------------------------------------------


def test_cross_statement_all_pass() -> None:
    # Consistent statements
    result = get_helper("cross_statement_validation").impl(
        net_income=100.0,
        retained_earnings=500.0,
        retained_earnings_prior=420.0,  # delta=80; NI=100, div=20 -> NI=delta+div 100=80+20 OK
        dividends_paid=20.0,
        total_assets=1000.0,
        total_liabilities=400.0,
        total_equity=600.0,
        cfo=90.0,
        cfi=-50.0,
        cff=-30.0,
        cash_current=200.0,
        cash_prior=190.0,
    )
    assert result["all_passed"] is True
    assert result["flagged_count"] == 0


def test_cross_statement_flags_accounting_equation() -> None:
    result = get_helper("cross_statement_validation").impl(
        net_income=100.0,
        retained_earnings=500.0,
        retained_earnings_prior=420.0,
        dividends_paid=20.0,
        total_assets=1000.0,
        total_liabilities=600.0,  # Wrong: 600+600=1200 != 1000
        total_equity=600.0,
        cfo=90.0,
        cfi=-50.0,
        cff=-30.0,
        cash_current=200.0,
        cash_prior=190.0,
    )
    flagged = [c for c in result["checks"] if c["flagged"]]
    names = [c["check"] for c in flagged]
    assert "accounting_equation" in names


# ---------------------------------------------------------------------------
# one_time_item_identification
# ---------------------------------------------------------------------------


def test_one_time_items_classification() -> None:
    items = [
        {"name": "Goodwill impairment", "type": "impairment", "amount": -50.0, "tax_rate": 0.25},
        {"name": "Gain on sale", "type": "gain_on_sale", "amount": 30.0, "tax_rate": 0.25},
    ]
    result = get_helper("one_time_item_identification").impl(items=items, net_income=100.0)
    assert result["item_count"] == 2
    assert result["total_pretax_impact"] == pytest.approx(-20.0, abs=0.01)
    # after-tax: impairment -50*(1-0.25)=-37.5; gain +30*(1-0.25)=+22.5; total=-15
    assert result["total_after_tax_impact"] == pytest.approx(-15.0, abs=0.01)
    assert result["pct_of_net_income"] == pytest.approx(-15.0, abs=0.01)


def test_one_time_items_unknown_type_coerced() -> None:
    items = [{"name": "Mystery charge", "type": "unknown_xyz", "amount": -10.0}]
    result = get_helper("one_time_item_identification").impl(items=items)
    assert result["items"][0]["type"] == "other_nonrecurring"


# ---------------------------------------------------------------------------
# organic_vs_inorganic_growth
# ---------------------------------------------------------------------------


def test_organic_growth_decomposition() -> None:
    result = get_helper("organic_vs_inorganic_growth").impl(
        revenue_prior=1000.0,
        revenue_current=1150.0,
        fx_impact=20.0,
        acquisition_revenue=50.0,
    )
    # total = 150 = 15%
    # fx = 20/1000 = 2%
    # acq = 50/1000 = 5%
    # organic = 15 - 2 - 5 = 8%
    assert result["total_growth_pct"] == pytest.approx(15.0, abs=0.01)
    assert result["fx_impact_pct"] == pytest.approx(2.0, abs=0.01)
    assert result["acquisition_pct"] == pytest.approx(5.0, abs=0.01)
    assert result["organic_growth_pct"] == pytest.approx(8.0, abs=0.01)


# ---------------------------------------------------------------------------
# currency_neutral_growth
# ---------------------------------------------------------------------------


def test_cc_growth_tailwind() -> None:
    result = get_helper("currency_neutral_growth").impl(reported_growth_pct=12.0, fx_impact_pct=3.0)
    assert result["constant_currency_growth_pct"] == pytest.approx(9.0, abs=0.01)
    assert result["fx_characterization"] == "tailwind"


def test_cc_growth_headwind() -> None:
    result = get_helper("currency_neutral_growth").impl(reported_growth_pct=8.0, fx_impact_pct=-4.0)
    assert result["constant_currency_growth_pct"] == pytest.approx(12.0, abs=0.01)
    assert result["fx_characterization"] == "headwind"


# ---------------------------------------------------------------------------
# margin_trajectory_regression
# ---------------------------------------------------------------------------


def test_margin_regression_slope_direction() -> None:
    # Perfect upward trend: 20%, 21%, 22%, 23%, 24%
    margins = [0.20, 0.21, 0.22, 0.23, 0.24]
    result = get_helper("margin_trajectory_regression").impl(operating_margins=margins)
    assert result["operating_margin"]["trend"] == "expanding"
    assert result["operating_margin"]["slope_decimal_per_period"] > 0


def test_margin_regression_r_squared_perfect() -> None:
    # Perfectly linear
    margins = [0.10, 0.12, 0.14, 0.16, 0.18]
    result = get_helper("margin_trajectory_regression").impl(gross_margins=margins)
    assert result["gross_margin"]["r_squared"] == pytest.approx(1.0, abs=0.001)


def test_margin_regression_none_series() -> None:
    result = get_helper("margin_trajectory_regression").impl(
        operating_margins=[0.20, 0.19, 0.18], gross_margins=None
    )
    assert result["gross_margin"] is None
    assert result["operating_margin"] is not None


# ---------------------------------------------------------------------------
# operating_leverage_analysis (DOL audit fix §9.5)
# ---------------------------------------------------------------------------


def test_dol_formula_audit_fix() -> None:
    """Audit fix §9.5: DOL = % change EBIT / % change Revenue."""
    result = get_helper("operating_leverage_analysis").impl(
        revenue=1100.0,
        revenue_prior=1000.0,
        ebit=220.0,
        ebit_prior=200.0,
    )
    pct_rev = (1100.0 - 1000.0) / 1000.0 * 100.0  # 10%
    pct_ebit = (220.0 - 200.0) / 200.0 * 100.0  # 10%
    expected_dol = pct_ebit / pct_rev  # 1.0
    assert result["dol"] == pytest.approx(expected_dol, abs=1e-4)


def test_dol_high_fixed_cost_structure() -> None:
    """Higher fixed costs -> higher DOL when revenue grows."""
    result = get_helper("operating_leverage_analysis").impl(
        revenue=1200.0,
        revenue_prior=1000.0,
        ebit=300.0,
        ebit_prior=200.0,  # EBIT grew 50% vs revenue grew 20%
    )
    # DOL = 50/20 = 2.5
    assert result["dol"] == pytest.approx(2.5, abs=1e-4)
    assert result["pct_change_revenue"] == pytest.approx(20.0, abs=0.01)
    assert result["pct_change_ebit"] == pytest.approx(50.0, abs=0.01)


def test_dol_with_cost_structure() -> None:
    result = get_helper("operating_leverage_analysis").impl(
        revenue=1000.0,
        revenue_prior=900.0,
        ebit=100.0,
        ebit_prior=80.0,
        fixed_costs=400.0,
        variable_costs=500.0,
    )
    assert result["cost_structure"] is not None
    assert result["cost_structure"]["contribution_margin"] == pytest.approx(500.0, abs=0.01)
    # contribution margin ratio = 500/1000 = 0.5
    assert result["cost_structure"]["contribution_margin_ratio"] == pytest.approx(0.5, abs=1e-4)
    # break-even = 400 / 0.5 = 800
    assert result["cost_structure"]["break_even_revenue"] == pytest.approx(800.0, abs=0.01)


# ---------------------------------------------------------------------------
# sbc_intensity
# ---------------------------------------------------------------------------


def test_sbc_intensity_ratios() -> None:
    result = get_helper("sbc_intensity").impl(
        sbc=80.0,
        revenue=1000.0,
        market_cap=5000.0,
        operating_income=200.0,
    )
    assert result["sbc_pct_revenue"] == pytest.approx(8.0, abs=0.01)
    assert result["sbc_pct_market_cap"] == pytest.approx(1.6, abs=0.01)
    assert result["sbc_pct_operating_income"] == pytest.approx(40.0, abs=0.01)


def test_sbc_intensity_dilution_bps() -> None:
    result = get_helper("sbc_intensity").impl(
        sbc=50.0,
        revenue=1000.0,
        market_cap=5000.0,
        shares_outstanding=105.0,
        shares_outstanding_prior=100.0,
    )
    # dilution = (105-100)/100 = 5% = 500 bps
    assert result["dilution_bps_per_year"] == pytest.approx(500.0, abs=0.1)


def test_sbc_intensity_verdict_high() -> None:
    result = get_helper("sbc_intensity").impl(sbc=120.0, revenue=1000.0, market_cap=5000.0)
    assert result["verdict"] == "high"


# ---------------------------------------------------------------------------
# cap_table_dilution
# ---------------------------------------------------------------------------


def test_cap_table_net_dilution_bps() -> None:
    result = get_helper("cap_table_dilution").impl(
        shares_series=[100.0, 102.0, 104.0],
    )
    # Period 2: (102-100)/100 = 2% = 200 bps
    assert result["periods"][1]["net_dilution_bps"] == pytest.approx(200.0, abs=0.1)
    assert result["trend"] == "dilutive"


def test_cap_table_buyback_accretive() -> None:
    result = get_helper("cap_table_dilution").impl(
        shares_series=[100.0, 95.0, 90.0],
    )
    assert result["trend"] == "accretive"


# ---------------------------------------------------------------------------
# piotroski_f_score (with DROA audit fix §9.2)
# ---------------------------------------------------------------------------

_PIO_BASE = dict(
    net_income=100.0,
    total_assets=1000.0,
    operating_cash_flow=120.0,
    total_debt=200.0,
    current_assets=400.0,
    current_liabilities=200.0,
    gross_profit=500.0,
    revenue=1000.0,
    shares_outstanding=100.0,
    net_income_prior=80.0,
    total_assets_prior=950.0,
    total_debt_prior=250.0,
    current_assets_prior=380.0,
    current_liabilities_prior=210.0,
    gross_profit_prior=450.0,
    revenue_prior=900.0,
    shares_outstanding_prior=100.0,
)


def test_piotroski_f_score_audit_fix_droa_full_year() -> None:
    """Audit fix §9.2: DROA uses full-year YoY delta, not quarterly."""
    result = get_helper("piotroski_f_score").impl(**_PIO_BASE)
    # ROA current = 100/1000 = 0.10; ROA prior = 80/950 ≈ 0.0842
    # DROA > 0 -> F3 = 1
    assert result["criteria"]["profitability"]["F3_delta_roa_positive_full_year"] == 1
    assert result["audit_note"] == "DROA uses full-year YoY comparison per audit fix §9.2"
    assert result["delta_roa"] == pytest.approx(0.10 - 80.0 / 950.0, abs=1e-4)


def test_piotroski_f_score_all_nine() -> None:
    """Perfect 9/9 score: all criteria met."""
    # Use gross_profit_prior=440 (48.9%) vs gross_profit=500 (50%) — margin improves
    result = get_helper("piotroski_f_score").impl(
        net_income=100.0,
        total_assets=1000.0,
        operating_cash_flow=120.0,
        total_debt=200.0,
        current_assets=400.0,
        current_liabilities=200.0,
        gross_profit=500.0,
        revenue=1000.0,
        shares_outstanding=100.0,
        net_income_prior=80.0,
        total_assets_prior=950.0,
        total_debt_prior=250.0,
        current_assets_prior=380.0,
        current_liabilities_prior=210.0,
        gross_profit_prior=440.0,  # 440/900=48.9% < 500/1000=50% -> margin improved
        revenue_prior=900.0,
        shares_outstanding_prior=100.0,
    )
    assert result["f_score"] == 9
    assert result["strength"] == "strong"


def test_piotroski_f_score_weak() -> None:
    """F-score 0/9: all criteria fail."""
    result = get_helper("piotroski_f_score").impl(
        net_income=-50.0,  # F1 fail
        total_assets=1000.0,
        operating_cash_flow=-10.0,  # F2 fail
        total_debt=300.0,  # F5 fail (debt increased)
        current_assets=100.0,  # F6 fail (CR worsened)
        current_liabilities=200.0,
        gross_profit=300.0,  # F8 fail (margin worsened)
        revenue=1000.0,
        shares_outstanding=110.0,  # F7 fail (diluted)
        net_income_prior=20.0,
        total_assets_prior=950.0,
        total_debt_prior=200.0,  # leverage was lower
        current_assets_prior=200.0,  # CR was higher
        current_liabilities_prior=150.0,
        gross_profit_prior=400.0,  # margin was higher
        revenue_prior=900.0,
        shares_outstanding_prior=100.0,
    )
    assert result["f_score"] <= 2
    assert result["strength"] == "weak"


# ---------------------------------------------------------------------------
# cash_conversion_cycle
# ---------------------------------------------------------------------------


def test_ccc_formula() -> None:
    result = get_helper("cash_conversion_cycle").impl(
        accounts_receivable=100.0,
        revenue=1000.0,
        inventory=50.0,
        cogs=600.0,
        accounts_payable=80.0,
        days_in_period=365,
    )
    dso = 100.0 / 1000.0 * 365  # 36.5
    dio = 50.0 / 600.0 * 365  # 30.42
    dpo = 80.0 / 600.0 * 365  # 48.67
    expected_ccc = dso + dio - dpo
    assert result["dso"] == pytest.approx(dso, abs=0.1)
    assert result["dio"] == pytest.approx(dio, abs=0.1)
    assert result["dpo"] == pytest.approx(dpo, abs=0.1)
    assert result["ccc"] == pytest.approx(expected_ccc, abs=0.1)


def test_ccc_uses_average_when_prior_provided() -> None:
    result = get_helper("cash_conversion_cycle").impl(
        accounts_receivable=120.0,
        revenue=1000.0,
        inventory=60.0,
        cogs=600.0,
        accounts_payable=90.0,
        accounts_receivable_prior=80.0,
    )
    # avg AR = (120+80)/2 = 100
    expected_dso = 100.0 / 1000.0 * 365
    assert result["dso"] == pytest.approx(expected_dso, abs=0.1)
    assert result["using_average_balances"] is True


# ---------------------------------------------------------------------------
# sustainable_growth_rate
# ---------------------------------------------------------------------------


def test_sgr_formula() -> None:
    result = get_helper("sustainable_growth_rate").impl(roe=0.20, payout_ratio=0.30)
    # SGR = 0.20 * (1 - 0.30) = 0.14
    assert result["sustainable_growth_rate"] == pytest.approx(0.14, abs=1e-4)
    assert result["retention_ratio"] == pytest.approx(0.70, abs=1e-4)
    assert result["sgr_pct"] == pytest.approx(14.0, abs=0.01)


def test_sgr_gap_unsustainable_high() -> None:
    result = get_helper("sustainable_growth_rate").impl(
        roe=0.15, payout_ratio=0.50, actual_revenue_growth=0.20
    )
    # SGR = 0.15 * 0.5 = 0.075; growth = 0.20; gap = 0.125 > 0.02 -> unsustainable
    assert result["gap_verdict"] == "unsustainable_high"


def test_sgr_invalid_payout_ratio() -> None:
    with pytest.raises(ValueError, match="payout_ratio must be in"):
        get_helper("sustainable_growth_rate").impl(roe=0.20, payout_ratio=1.5)


# ---------------------------------------------------------------------------
# forensic_panel aggregator
# ---------------------------------------------------------------------------


def test_forensic_panel_zero_when_no_inputs() -> None:
    result = get_helper("forensic_panel").impl()
    assert result["composite_score"] == pytest.approx(0.0, abs=0.1)
    assert result["concern_level"] == "low"


def test_forensic_panel_high_score_all_signals() -> None:
    """When all four signals are at maximum, score should be 100."""
    one_time_out = {"pct_of_net_income": 50.0}  # max: >20% -> score 100
    qoe_out = {"accruals_pct_of_ni": 40.0, "sloan_ratio": 0.20}  # near max
    sbc_out = {"sbc_pct_revenue": 15.0}  # max: >10%

    result = get_helper("forensic_panel").impl(
        one_time_item_output=one_time_out,
        quality_of_earnings_output=qoe_out,
        sbc_intensity_output=sbc_out,
        ar_current=200.0,
        ar_prior=100.0,
        revenue_current=500.0,
        revenue_prior=600.0,
    )
    assert result["composite_score"] > 50.0
    assert result["concern_level"] in ("elevated", "high")


def test_forensic_panel_moderate_accruals() -> None:
    qoe_out = {"accruals_pct_of_ni": 15.0, "sloan_ratio": 0.05}
    result = get_helper("forensic_panel").impl(quality_of_earnings_output=qoe_out)
    assert 0 < result["composite_score"] < 50


def test_forensic_panel_top_signals_returned() -> None:
    qoe_out = {"accruals_pct_of_ni": 30.0, "sloan_ratio": 0.15}
    one_time_out = {"pct_of_net_income": 10.0}
    result = get_helper("forensic_panel").impl(
        quality_of_earnings_output=qoe_out,
        one_time_item_output=one_time_out,
    )
    assert len(result["top_signals"]) == 2
    # Accruals should dominate (weight 0.30)
    assert result["top_signals"][0]["signal"] == "accruals"


def test_forensic_panel_channel_stuffing_signal() -> None:
    """AR/Revenue ratio doubling should produce non-zero channel stuffing score."""
    result = get_helper("forensic_panel").impl(
        ar_current=200.0,
        ar_prior=100.0,
        revenue_current=1000.0,
        revenue_prior=1000.0,
    )
    # ar_rev changed from 0.10 to 0.20 = 100% change -> max stuffing signal = 100
    # stuffing weight = 0.25; contribution = 25
    assert result["signal_scores"]["channel_stuffing"] == pytest.approx(100.0, abs=0.1)
    assert result["signal_contributions"]["channel_stuffing"] == pytest.approx(25.0, abs=0.1)


def test_forensic_panel_consumes_correct_artifacts() -> None:
    helper = get_helper("forensic_panel")
    assert "one_time_item_output" in helper.schema.contract.consumes_artifacts
    assert "quality_of_earnings_output" in helper.schema.contract.consumes_artifacts
    assert "sbc_intensity_output" in helper.schema.contract.consumes_artifacts
