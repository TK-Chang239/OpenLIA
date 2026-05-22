"""Tests for PR 2.7: credit_solvency_panel, five_step_dupont, debt_maturity_ladder.

Covers:
  - Registration of all 3 helpers
  - Credit: Debt/EBITDA = 5x triggers warning
  - Credit: synthetic rating mapping (AAA at low leverage, B at high)
  - Credit: FRED spread integration (mocked)
  - DuPont 5-step: ROE reconciles from product of 5 components (float tolerance)
  - DuPont: known textbook inputs
  - Debt ladder: refinancing wall detection at 30% concentration triggers warning
  - Debt ladder: WAM calculation correct
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

# ---------------------------------------------------------------------------
# Registration checks
# ---------------------------------------------------------------------------

CREDIT_HELPERS = [
    "credit_solvency_panel",
    "five_step_dupont",
    "debt_maturity_ladder",
]


@pytest.mark.parametrize("name", CREDIT_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


@pytest.mark.parametrize("name", CREDIT_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) >= 1


# ---------------------------------------------------------------------------
# credit_solvency_panel
# ---------------------------------------------------------------------------


def _credit_inputs(
    debt: float = 200.0,
    ebitda: float = 100.0,
    ebit: float = 80.0,
    interest: float = 20.0,
    cash: float = 30.0,
    equity: float = 250.0,
    n: int = 5,
) -> dict:
    """Build minimal credit inputs for n periods."""
    return dict(
        historical_ebit=[ebit] * n,
        historical_ebitda=[ebitda] * n,
        historical_capex=[10.0] * n,
        historical_interest_expense=[interest] * n,
        historical_total_debt=[debt] * n,
        historical_cash=[cash] * n,
        historical_total_equity=[equity] * n,
    )


def test_credit_solvency_registers() -> None:
    assert get_helper("credit_solvency_panel") is not None


def test_credit_solvency_high_debt_ebitda_warning() -> None:
    """Debt/EBITDA = 5x (500/100) triggers a warning."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs(debt=500.0, ebitda=100.0))
    assert result["current_period"]["debt_to_ebitda"] == pytest.approx(5.0, abs=1e-4)
    warning_text = " ".join(result["warnings"])
    assert "4x" in warning_text or "Debt/EBITDA" in warning_text


def test_credit_solvency_low_coverage_warning() -> None:
    """EBIT coverage = 1.5x (below 3x) triggers a warning."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs(ebit=30.0, interest=20.0))
    cov = result["current_period"]["interest_coverage_ebit"]
    assert isinstance(cov, float)
    assert cov == pytest.approx(1.5, abs=1e-4)
    warning_text = " ".join(result["warnings"])
    assert "3x" in warning_text or "coverage" in warning_text.lower()


def test_credit_solvency_implied_rating_aaa_at_low_leverage() -> None:
    """Low leverage (Debt/EBITDA 0.5x) + high coverage (20x) -> AAA proxy."""
    result = get_helper("credit_solvency_panel").impl(
        **_credit_inputs(debt=50.0, ebitda=100.0, ebit=80.0, interest=4.0)
    )
    # Debt/EBITDA = 0.5, EBIT/Interest = 20.0 -> should map to AAA
    assert "AAA" in result["implied_rating_proxy"]
    assert result["credit_score"] == 100


def test_credit_solvency_implied_rating_b_at_high_leverage() -> None:
    """Debt/EBITDA 4.5x, EBIT coverage 2x -> B rating proxy."""
    result = get_helper("credit_solvency_panel").impl(
        **_credit_inputs(debt=450.0, ebitda=100.0, ebit=40.0, interest=20.0)
    )
    # Debt/EBITDA = 4.5, EBIT/Interest = 2.0
    rating_proxy = result["implied_rating_proxy"]
    # Should be B (coverage 2.0 in 1.5-3.0 AND debt/ebitda 4.5 in 4.0-5.0)
    assert "B" in rating_proxy
    assert result["credit_score"] <= 45  # B or below


def test_credit_solvency_ccc_at_extreme_leverage() -> None:
    """Debt/EBITDA > 5x -> CCC proxy."""
    result = get_helper("credit_solvency_panel").impl(
        **_credit_inputs(debt=600.0, ebitda=100.0, ebit=30.0, interest=25.0)
    )
    assert "CCC" in result["implied_rating_proxy"]
    assert result["credit_score"] <= 28


def test_credit_solvency_rating_proxy_disclaimer() -> None:
    """implied_rating_proxy must include 'proxy' and 'not an actual rating'."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs())
    assert "proxy" in result["implied_rating_proxy"].lower()
    assert "not an actual rating" in result["implied_rating_proxy"].lower()


def test_credit_solvency_fred_spread_integration() -> None:
    """FRED spreads dict attaches fred_spread_context to output."""
    mock_fred = {
        "hy_oas": 4.5,
        "ig_oas": 1.2,
        "treasury_10y": 4.3,
        "spread_differential": 3.3,
        "as_of": "2026-05-22",
        "source": "FRED via ICE BofA",
    }
    result = get_helper("credit_solvency_panel").impl(
        **_credit_inputs(debt=200.0, ebitda=100.0, ebit=80.0, interest=10.0),
        fred_spreads=mock_fred,
    )
    assert "fred_spread_context" in result
    ctx = result["fred_spread_context"]
    assert ctx["hy_oas_pct"] == 4.5
    assert ctx["ig_oas_pct"] == 1.2
    assert ctx["as_of"] == "2026-05-22"
    # Should identify IG spread as relevant for investment-grade name
    assert ctx["implied_category"] in (
        "investment_grade_strong",
        "investment_grade_adequate",
        "high_yield",
        "distressed",
    )


def test_credit_solvency_fred_without_spreads_no_context() -> None:
    """No fred_spreads -> no fred_spread_context key."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs())
    assert "fred_spread_context" not in result


def test_credit_solvency_infinite_coverage_zero_interest() -> None:
    """Zero interest expense -> coverage = 'infinite'."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs(interest=0.0))
    assert result["current_period"]["interest_coverage_ebit"] == "infinite"
    assert result["current_period"]["interest_coverage_ebitda"] == "infinite"


def test_credit_solvency_book_insolvent() -> None:
    """Negative equity -> 'book_insolvent' in debt_to_equity."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs(equity=-50.0))
    assert result["current_period"]["debt_to_equity"] == "book_insolvent"
    warning_text = " ".join(result["warnings"])
    assert "insolvent" in warning_text.lower()


def test_credit_solvency_min_4_periods_enforced() -> None:
    with pytest.raises(ValueError, match="at least 4"):
        get_helper("credit_solvency_panel").impl(**_credit_inputs(n=3))


def test_credit_solvency_series_length_mismatch() -> None:
    inputs = _credit_inputs(n=5)
    inputs["historical_ebitda"] = [100.0] * 4  # wrong length
    with pytest.raises(ValueError, match="length"):
        get_helper("credit_solvency_panel").impl(**inputs)


def test_credit_solvency_net_debt_ratio_correct() -> None:
    """Net Debt/EBITDA = (debt - cash) / ebitda."""
    result = get_helper("credit_solvency_panel").impl(
        **_credit_inputs(debt=300.0, cash=50.0, ebitda=100.0)
    )
    expected_net_debt_ebitda = (300.0 - 50.0) / 100.0
    assert result["current_period"]["net_debt_to_ebitda"] == pytest.approx(
        expected_net_debt_ebitda, abs=1e-4
    )


def test_credit_solvency_debt_to_capital_formula() -> None:
    """Debt/Capital = debt / (debt + equity)."""
    result = get_helper("credit_solvency_panel").impl(**_credit_inputs(debt=200.0, equity=400.0))
    expected = 200.0 / (200.0 + 400.0)
    assert result["current_period"]["debt_to_capital"] == pytest.approx(expected, abs=1e-4)


def test_credit_solvency_liquidity_ratios() -> None:
    """Current ratio and quick ratio computed when optional inputs provided."""
    result = get_helper("credit_solvency_panel").impl(
        historical_ebit=[80.0] * 5,
        historical_ebitda=[100.0] * 5,
        historical_capex=[10.0] * 5,
        historical_interest_expense=[10.0] * 5,
        historical_total_debt=[200.0] * 5,
        historical_cash=[50.0] * 5,
        historical_total_equity=[300.0] * 5,
        historical_current_assets=[150.0] * 5,
        historical_current_liabilities=[100.0] * 5,
        historical_quick_assets=[80.0] * 5,
        historical_st_debt=[30.0] * 5,
    )
    assert result["current_period"]["current_ratio"] == pytest.approx(1.5, abs=1e-4)
    assert result["current_period"]["quick_ratio"] == pytest.approx(0.8, abs=1e-4)
    assert result["current_period"]["cash_to_st_debt"] == pytest.approx(50.0 / 30.0, abs=1e-4)


# ---------------------------------------------------------------------------
# five_step_dupont
# ---------------------------------------------------------------------------


def _dupont_inputs(
    ni: float = 150.0,
    ebt: float = 190.0,
    ebit: float = 200.0,
    sales: float = 1000.0,
    assets: float = 800.0,
    equity: float = 400.0,
    n: int = 5,
) -> dict:
    """Build 5-period DuPont inputs."""
    return dict(
        historical_net_income=[ni] * n,
        historical_ebt=[ebt] * n,
        historical_ebit=[ebit] * n,
        historical_sales=[sales] * n,
        historical_total_assets=[assets] * n,
        historical_total_equity=[equity] * n,
    )


def test_dupont_registers() -> None:
    assert get_helper("five_step_dupont") is not None


def test_dupont_roe_reconciles_from_product_of_5() -> None:
    """Product of 5 components must equal ROE within 0.5% tolerance."""
    result = get_helper("five_step_dupont").impl(**_dupont_inputs())
    cp = result["current_period"]
    product = (
        cp["tax_burden"]
        * cp["interest_burden"]
        * cp["operating_margin"]
        * cp["asset_turnover"]
        * cp["equity_multiplier"]
    )
    assert product == pytest.approx(cp["roe"], rel=0.005)


def test_dupont_known_textbook_example() -> None:
    """Textbook verification:
    NI=150, EBT=190, EBIT=200, Sales=1000, Assets=800, Equity=400
    tax_burden = 150/190 = 0.7895
    interest_burden = 190/200 = 0.95
    operating_margin = 200/1000 = 0.20
    asset_turnover = 1000/800 = 1.25
    equity_multiplier = 800/400 = 2.00
    ROE = 0.7895 * 0.95 * 0.20 * 1.25 * 2.00 = 0.375
    """
    result = get_helper("five_step_dupont").impl(**_dupont_inputs())
    cp = result["current_period"]
    assert cp["tax_burden"] == pytest.approx(150.0 / 190.0, abs=1e-4)
    assert cp["interest_burden"] == pytest.approx(190.0 / 200.0, abs=1e-4)
    assert cp["operating_margin"] == pytest.approx(200.0 / 1000.0, abs=1e-4)
    assert cp["asset_turnover"] == pytest.approx(1000.0 / 800.0, abs=1e-4)
    assert cp["equity_multiplier"] == pytest.approx(800.0 / 400.0, abs=1e-4)
    expected_roe = (
        (150.0 / 190.0) * (190.0 / 200.0) * (200.0 / 1000.0) * (1000.0 / 800.0) * (800.0 / 400.0)
    )
    assert cp["roe"] == pytest.approx(expected_roe, abs=1e-4)


def test_dupont_3step_roe_reconciles() -> None:
    """3-step ROE = NI_margin * asset_turnover * equity_multiplier."""
    result = get_helper("five_step_dupont").impl(**_dupont_inputs())
    cp3 = result["three_step"]["current_period"]
    expected = cp3["ni_margin"] * cp3["asset_turnover"] * cp3["equity_multiplier"]
    assert cp3["roe"] == pytest.approx(expected, abs=1e-4)


def test_dupont_3step_roe_matches_5step_roe() -> None:
    """3-step and 5-step ROE must agree (both are NI/Equity)."""
    result = get_helper("five_step_dupont").impl(**_dupont_inputs())
    roe_5 = result["current_period"]["roe"]
    roe_3 = result["three_step"]["current_period"]["roe"]
    assert roe_5 == pytest.approx(roe_3, abs=1e-4)


def test_dupont_roe_change_decomposition_present() -> None:
    """five_year_change_in_roe populated when improvement from oldest to newest."""
    # Improve operating margin from 15% to 25% over 5 years
    result = get_helper("five_step_dupont").impl(
        historical_net_income=[100.0, 110.0, 120.0, 135.0, 150.0],
        historical_ebt=[130.0, 140.0, 150.0, 165.0, 180.0],
        historical_ebit=[140.0, 150.0, 160.0, 175.0, 190.0],
        historical_sales=[900.0, 950.0, 1000.0, 1000.0, 1000.0],
        historical_total_assets=[800.0] * 5,
        historical_total_equity=[400.0] * 5,
    )
    chg = result["five_year_change_in_roe"]
    assert "total" in chg
    assert "drivers" in chg
    # ROE should have increased
    assert chg["total"] > 0


def test_dupont_negative_equity_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        get_helper("five_step_dupont").impl(**_dupont_inputs(equity=-100.0))


def test_dupont_zero_sales_raises() -> None:
    with pytest.raises(ValueError, match="non-zero"):
        get_helper("five_step_dupont").impl(**_dupont_inputs(sales=0.0))


def test_dupont_min_5_periods_enforced() -> None:
    with pytest.raises(ValueError, match="at least 5"):
        get_helper("five_step_dupont").impl(**_dupont_inputs(n=4))


def test_dupont_series_mismatch_raises() -> None:
    inputs = _dupont_inputs(n=5)
    inputs["historical_ebt"] = [190.0] * 4  # wrong length
    with pytest.raises(ValueError, match="length"):
        get_helper("five_step_dupont").impl(**inputs)


def test_dupont_all_5_factors_present_in_decomposition() -> None:
    result = get_helper("five_step_dupont").impl(**_dupont_inputs())
    for factor in [
        "tax_burden",
        "interest_burden",
        "operating_margin",
        "asset_turnover",
        "equity_multiplier",
        "roe",
    ]:
        assert factor in result["decomposition"]
        assert len(result["decomposition"][factor]) == 5


def test_dupont_high_leverage_roi_interpretation() -> None:
    """If equity multiplier drives ROE increase, narrative should mention leverage."""
    # Strong ROE growth driven by doubling leverage
    result = get_helper("five_step_dupont").impl(
        historical_net_income=[50.0, 50.0, 50.0, 50.0, 50.0],
        historical_ebt=[60.0, 60.0, 60.0, 60.0, 60.0],
        historical_ebit=[65.0, 65.0, 65.0, 65.0, 65.0],
        historical_sales=[500.0] * 5,
        historical_total_assets=[400.0, 500.0, 600.0, 700.0, 800.0],
        historical_total_equity=[200.0, 200.0, 200.0, 200.0, 200.0],  # leverage doubles
    )
    chg = result["five_year_change_in_roe"]
    # Equity multiplier contribution should be positive and dominant
    drivers = chg.get("drivers", {})
    assert drivers.get("equity_multiplier", 0) > 0


# ---------------------------------------------------------------------------
# debt_maturity_ladder
# ---------------------------------------------------------------------------


def _instruments_no_wall() -> list[dict]:
    """5 bonds spread evenly across years — no single wall."""
    return [
        {"name": "Bond 2026", "principal": 200.0, "coupon": 0.04, "maturity": "2026-06-30"},
        {"name": "Bond 2027", "principal": 200.0, "coupon": 0.045, "maturity": "2027-06-30"},
        {"name": "Bond 2028", "principal": 200.0, "coupon": 0.05, "maturity": "2028-06-30"},
        {"name": "Bond 2029", "principal": 200.0, "coupon": 0.052, "maturity": "2029-06-30"},
        {"name": "Bond 2030", "principal": 200.0, "coupon": 0.055, "maturity": "2030-06-30"},
    ]


def _instruments_with_wall() -> list[dict]:
    """Total = 1000; 300 in 2028 = 30% -> triggers wall."""
    return [
        {"name": "Sr Notes 2026", "principal": 100.0, "coupon": 0.04, "maturity": "2026-04-01"},
        {"name": "Term Loan 2027", "principal": 150.0, "coupon": 0.055, "maturity": "2027-09-15"},
        {
            "name": "5.25% Notes 2028",
            "principal": 300.0,
            "coupon": 0.0525,
            "maturity": "2028-04-15",
        },
        {"name": "4.8% Notes 2029", "principal": 200.0, "coupon": 0.048, "maturity": "2029-03-01"},
        {"name": "5.5% Notes 2031", "principal": 250.0, "coupon": 0.055, "maturity": "2031-06-01"},
    ]


def test_debt_ladder_registers() -> None:
    assert get_helper("debt_maturity_ladder") is not None


def test_debt_ladder_wam_correct() -> None:
    """WAM = sum(principal_i * years_i) / sum(principal_i).

    With equal principal amounts spread across 5 years from 2026-2030,
    as_of 2026-01-01, WAM should be ~2-3 years (approximate; exact depends on day count).
    """
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_no_wall(),
        as_of_date="2026-01-01",
    )
    wam = result["weighted_avg_maturity_years"]
    assert wam is not None
    # 5 equal instruments maturing between mid-2026 and mid-2030
    # Approximate check: WAM should be between 1 and 5 years
    assert 1.0 <= wam <= 5.0


def test_debt_ladder_wam_exact() -> None:
    """Verify WAM with two known instruments."""
    # Bond A: 1000 principal, matures exactly 2 years from as_of
    # Bond B: 1000 principal, matures exactly 4 years from as_of
    # WAM = (1000 * 2 + 1000 * 4) / 2000 = 3.0 years
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=[
            {"name": "Bond A", "principal": 1000.0, "coupon": 0.05, "maturity": "2028-01-01"},
            {"name": "Bond B", "principal": 1000.0, "coupon": 0.05, "maturity": "2030-01-01"},
        ],
        as_of_date="2026-01-01",
    )
    # Allow fractional year tolerance (day count differences)
    assert result["weighted_avg_maturity_years"] == pytest.approx(3.0, abs=0.05)


def test_debt_ladder_no_refi_wall() -> None:
    """Evenly spread instruments do not trigger a wall."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_no_wall(),
        as_of_date="2026-01-01",
    )
    assert result["refi_wall"]["detected"] is False


def test_debt_ladder_refi_wall_at_30_pct() -> None:
    """300/1000 = 30% in 2028 triggers refi wall (threshold 25%)."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_with_wall(),
        as_of_date="2026-01-01",
    )
    assert result["refi_wall"]["detected"] is True
    assert result["refi_wall"]["year"] == "2028"
    assert result["refi_wall"]["pct_of_total_debt"] == pytest.approx(0.30, abs=1e-3)


def test_debt_ladder_refi_wall_warning_text() -> None:
    """Wall detection produces a warning string referencing 2028."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_with_wall(),
        as_of_date="2026-01-01",
    )
    warnings = result["warnings"]
    assert any("2028" in w for w in warnings)


def test_debt_ladder_total_debt_sum() -> None:
    """total_debt must equal sum of all principals."""
    instruments = _instruments_with_wall()
    expected_total = sum(i["principal"] for i in instruments)
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=instruments,
        as_of_date="2026-01-01",
    )
    assert result["total_debt"] == pytest.approx(expected_total, abs=0.01)


def test_debt_ladder_ladder_sum_equals_total() -> None:
    """Sum of principal_due across all ladder rows = total_debt."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_with_wall(),
        as_of_date="2026-01-01",
    )
    ladder_sum = sum(row["principal_due"] for row in result["ladder"])
    assert ladder_sum == pytest.approx(result["total_debt"], abs=0.01)


def test_debt_ladder_wac_correct() -> None:
    """WAC = sum(principal_i * coupon_i) / sum(principal_i)."""
    instruments = [
        {"name": "Bond A", "principal": 500.0, "coupon": 0.04, "maturity": "2028-01-01"},
        {"name": "Bond B", "principal": 500.0, "coupon": 0.06, "maturity": "2030-01-01"},
    ]
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=instruments,
        as_of_date="2026-01-01",
    )
    expected_wac = (500 * 0.04 + 500 * 0.06) / 1000
    assert result["weighted_avg_coupon"] == pytest.approx(expected_wac, abs=1e-5)


def test_debt_ladder_stress_test_populated_when_wall_detected() -> None:
    """refi_stress_test populated when wall detected."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_with_wall(),
        as_of_date="2026-01-01",
        refi_rate_shock=0.02,
        current_pretax_cost_of_debt=0.05,
        current_ebit=500.0,
    )
    stress = result["refi_stress_test"]
    assert stress["shock_bps"] == 200
    # incremental_interest = 300 * 0.02 = 6.0
    assert stress["incremental_annual_interest"] == pytest.approx(6.0, abs=0.01)
    assert stress["implied_new_cost_of_debt"] == pytest.approx(0.07, abs=1e-5)
    assert stress["incremental_interest_pct_of_ebit"] == pytest.approx(6.0 / 500.0, abs=1e-5)


def test_debt_ladder_empty_instruments_raises() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        get_helper("debt_maturity_ladder").impl(
            debt_instruments=[],
            as_of_date="2026-01-01",
        )


def test_debt_ladder_refinancing_risk_score_in_range() -> None:
    """Refinancing risk score must be 0-100."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=_instruments_with_wall(),
        as_of_date="2026-01-01",
    )
    score = result["refinancing_risk_score"]
    assert 0 <= score <= 100


def test_debt_ladder_bucket_11plus() -> None:
    """Instruments maturing > 10 years out go into '11+' bucket."""
    result = get_helper("debt_maturity_ladder").impl(
        debt_instruments=[
            {
                "name": "Long Bond 2040",
                "principal": 500.0,
                "coupon": 0.05,
                "maturity": "2040-01-01",
            },
        ],
        as_of_date="2026-01-01",
    )
    years = {row["year"] for row in result["ladder"]}
    assert "11+" in years
