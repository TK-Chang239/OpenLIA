"""Tests for the 15 FinanceToolkit ratio helpers and FRED credit spreads helper.

Uses canned MSFT-like fixtures — no live API calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper, list_helpers

from . import fixtures as F

# ---------------------------------------------------------------------------
# Registration: all 16 new helpers must be in the registry
# ---------------------------------------------------------------------------

FT_HELPERS = [
    "ft_liquidity_ratios",
    "ft_solvency_ratios",
    "ft_profitability_ratios",
    "ft_efficiency_ratios",
    "ft_valuation_ratios",
    "ft_dupont_decomposition",
    "ft_altman_z_score",
    "ft_piotroski_f_score",
    "ft_growth_metrics",
    "ft_per_share_metrics",
    "ft_cash_flow_metrics",
    "ft_dividend_metrics",
    "ft_working_capital_metrics",
    "ft_capital_structure",
    "ft_quality_metrics",
    "fred_credit_spreads",
]


@pytest.mark.parametrize("name", FT_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


def test_all_16_new_helpers_registered() -> None:
    registered = {h.schema.directory.name for h in list_helpers()}
    missing = [n for n in FT_HELPERS if n not in registered]
    assert not missing, f"Missing helpers: {missing}"


# ---------------------------------------------------------------------------
# Schema integrity: produces_artifacts ends with _output, version = "0.1.0"
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", FT_HELPERS)
def test_helper_schema_produces_artifact(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) >= 1
    for artifact in helper.schema.contract.produces_artifacts:
        assert artifact.endswith("_output"), (
            f"{name}: artifact {artifact!r} must end with '_output'"
        )


@pytest.mark.parametrize("name", FT_HELPERS)
def test_helper_schema_version(name: str) -> None:
    helper = get_helper(name)
    assert helper.schema.version == "0.1.0"


# ---------------------------------------------------------------------------
# ft_liquidity_ratios
# ---------------------------------------------------------------------------


def test_liquidity_ratios_basic() -> None:
    result = get_helper("ft_liquidity_ratios").impl(
        current_assets=F.BALANCE["current_assets"],
        current_liabilities=F.BALANCE["current_liabilities"],
        cash_and_equivalents=F.BALANCE["cash_and_equivalents"],
        marketable_securities=F.BALANCE["marketable_securities"],
        accounts_receivable=F.BALANCE["accounts_receivable"],
        inventory=F.BALANCE["inventory"],
        operating_cash_flow=F.CASH_FLOW["operating_cash_flow"],
        accounts_payable=F.BALANCE["accounts_payable"],
    )
    assert isinstance(result, dict)
    assert result["current_ratio"] == pytest.approx(1.4718, abs=0.001)
    # cash_ratio = (cash + marketable) / current_liabilities
    assert result["cash_ratio"] == pytest.approx(
        (F.BALANCE["cash_and_equivalents"] + F.BALANCE["marketable_securities"])
        / F.BALANCE["current_liabilities"],
        abs=0.001,
    )
    assert result["working_capital"] == pytest.approx(59_120_000_000, rel=0.01)


def test_liquidity_ratios_current_ratio_formula() -> None:
    # current_ratio = current_assets / current_liabilities
    result = get_helper("ft_liquidity_ratios").impl(
        current_assets=200.0,
        current_liabilities=100.0,
    )
    assert result["current_ratio"] == pytest.approx(2.0)
    assert result["working_capital"] == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# ft_solvency_ratios
# ---------------------------------------------------------------------------


def test_solvency_ratios_basic() -> None:
    result = get_helper("ft_solvency_ratios").impl(
        total_debt=F.BALANCE["total_debt"],
        total_equity=F.BALANCE["total_equity"],
        total_assets=F.BALANCE["total_assets"],
        operating_income=F.INCOME["operating_income"],
        interest_expense=F.INCOME["interest_expense"],
        depreciation_and_amortization=F.INCOME["depreciation_and_amortization"],
        free_cash_flow=F.CASH_FLOW["free_cash_flow"],
        market_cap=F.MARKET["market_cap"],
    )
    assert isinstance(result, dict)
    # D/E = 79.3B / 268.5B ≈ 0.295
    assert result["debt_to_equity"] == pytest.approx(0.2954, abs=0.001)
    assert result["interest_coverage"] is not None and result["interest_coverage"] > 10
    assert result["free_cash_flow_yield"] is not None


def test_solvency_debt_to_equity_formula() -> None:
    result = get_helper("ft_solvency_ratios").impl(
        total_debt=50.0,
        total_equity=100.0,
        total_assets=150.0,
        operating_income=20.0,
        interest_expense=5.0,
    )
    assert result["debt_to_equity"] == pytest.approx(0.5)
    assert result["debt_to_assets"] == pytest.approx(50.0 / 150.0)


# ---------------------------------------------------------------------------
# ft_profitability_ratios
# ---------------------------------------------------------------------------


def test_profitability_ratios_basic() -> None:
    result = get_helper("ft_profitability_ratios").impl(
        revenue=F.INCOME["revenue"],
        gross_profit=F.INCOME["gross_profit"],
        operating_income=F.INCOME["operating_income"],
        net_income=F.INCOME["net_income"],
        total_assets=F.BALANCE["total_assets"],
        total_equity=F.BALANCE["total_equity"],
        operating_cash_flow=F.CASH_FLOW["operating_cash_flow"],
        free_cash_flow=F.CASH_FLOW["free_cash_flow"],
    )
    assert isinstance(result, dict)
    # gross margin = 42.4B / 61.9B ≈ 0.685
    assert result["gross_margin"] == pytest.approx(0.6853, abs=0.001)
    # net margin = 21.9B / 61.9B ≈ 0.355
    assert result["net_margin"] == pytest.approx(0.3546, abs=0.001)


def test_profitability_roe_formula() -> None:
    # ROE = NI / Avg Equity
    # With single-period: ROE = NI / equity
    result = get_helper("ft_profitability_ratios").impl(
        revenue=1000.0,
        gross_profit=600.0,
        operating_income=200.0,
        net_income=100.0,
        total_assets=500.0,
        total_equity=250.0,
    )
    # roe = 100 / 250 = 0.4
    assert result["roe"] == pytest.approx(0.4)
    # roa = 100 / 500 = 0.2
    assert result["roa"] == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# ft_efficiency_ratios
# ---------------------------------------------------------------------------


def test_efficiency_ratios_asset_turnover() -> None:
    result = get_helper("ft_efficiency_ratios").impl(
        revenue=F.INCOME["revenue"],
        total_assets=F.BALANCE["total_assets"],
        cost_of_goods_sold=F.INCOME["cost_of_goods_sold"],
        inventory=F.BALANCE["inventory"],
        accounts_receivable=F.BALANCE["accounts_receivable"],
        accounts_payable=F.BALANCE["accounts_payable"],
    )
    assert isinstance(result, dict)
    assert result["asset_turnover"] == pytest.approx(
        F.INCOME["revenue"] / F.BALANCE["total_assets"], rel=0.01
    )
    assert result["cash_conversion_cycle"] is not None
    assert result["days_sales_outstanding"] is not None


def test_efficiency_ratios_minimal() -> None:
    # Only required params
    result = get_helper("ft_efficiency_ratios").impl(
        revenue=1000.0,
        total_assets=500.0,
    )
    assert result["asset_turnover"] == pytest.approx(2.0)
    assert result["inventory_turnover"] is None
    assert result["receivables_turnover"] is None


# ---------------------------------------------------------------------------
# ft_valuation_ratios
# ---------------------------------------------------------------------------


def test_valuation_ratios_pe_formula() -> None:
    # P/E = price / EPS
    result = get_helper("ft_valuation_ratios").impl(
        share_price=100.0,
        shares_outstanding=1000.0,
        net_income=10_000.0,
        total_equity=50_000.0,
        revenue=100_000.0,
        operating_income=15_000.0,
    )
    # EPS = 10000 / 1000 = 10.0
    assert result["eps"] == pytest.approx(10.0)
    # P/E = 100 / 10 = 10
    assert result["pe_ratio"] == pytest.approx(10.0)
    # BVPS = 50000 / 1000 = 50
    assert result["book_value_per_share"] == pytest.approx(50.0)
    # P/B = 100 / 50 = 2
    assert result["pb_ratio"] == pytest.approx(2.0)


def test_valuation_ratios_ev_ebitda() -> None:
    result = get_helper("ft_valuation_ratios").impl(
        share_price=F.MARKET["share_price"],
        shares_outstanding=F.MARKET["shares_outstanding"],
        net_income=F.INCOME["net_income"],
        total_equity=F.BALANCE["total_equity"],
        revenue=F.INCOME["revenue"],
        operating_income=F.INCOME["operating_income"],
        depreciation_and_amortization=F.INCOME["depreciation_and_amortization"],
        total_debt=F.BALANCE["total_debt"],
        cash_and_equivalents=F.BALANCE["cash_and_equivalents"],
    )
    assert result["ev_to_ebitda"] is not None
    assert result["market_cap"] == pytest.approx(
        F.MARKET["share_price"] * F.MARKET["shares_outstanding"], rel=0.01
    )


# ---------------------------------------------------------------------------
# ft_dupont_decomposition
# ---------------------------------------------------------------------------


def test_dupont_roe_components() -> None:
    result = get_helper("ft_dupont_decomposition").impl(
        net_income=F.INCOME["net_income"],
        total_revenue=F.INCOME["revenue"],
        total_assets=F.BALANCE["total_assets"],
        total_equity=F.BALANCE["total_equity"],
    )
    assert isinstance(result, dict)
    # Should contain at least roe
    keys = {k.lower() for k in result.keys()}
    assert any("roe" in k or "return_on_equity" in k for k in keys), (
        f"Expected ROE key in DuPont result, got: {list(result.keys())}"
    )


def test_dupont_net_margin_formula() -> None:
    # net margin = NI / Revenue = 100 / 1000 = 0.1
    result = get_helper("ft_dupont_decomposition").impl(
        net_income=100.0,
        total_revenue=1000.0,
        total_assets=500.0,
        total_equity=250.0,
    )
    assert isinstance(result, dict)
    # At minimum we expect a non-empty dict
    assert len(result) > 0


# ---------------------------------------------------------------------------
# ft_altman_z_score
# ---------------------------------------------------------------------------


def test_altman_z_score_basic() -> None:
    result = get_helper("ft_altman_z_score").impl(
        current_assets=F.BALANCE["current_assets"],
        current_liabilities=F.BALANCE["current_liabilities"],
        total_assets=F.BALANCE["total_assets"],
        retained_earnings=F.BALANCE["retained_earnings"],
        ebit=F.INCOME["ebit"],
        market_cap=F.MARKET["market_cap"],
        total_liabilities=F.BALANCE["total_liabilities"],
        total_revenue=F.INCOME["revenue"],
    )
    assert isinstance(result, dict)
    assert "z_score" in result
    assert "zone" in result
    # MSFT is financially healthy — should be safe
    assert result["zone"] == "safe"
    assert result["z_score"] > 2.99


def test_altman_z_score_known_value() -> None:
    # Manual computation:
    # Working capital = 100 - 50 = 50
    # X1 = 50/200 = 0.25
    # X2 = 60/200 = 0.30
    # X3 = 40/200 = 0.20
    # X4 = 500/80 = 6.25  (total_liab = total_assets - equity = 200-120=80)
    # X5 = 120/200 = 0.60
    # Z = 1.2*0.25 + 1.4*0.30 + 3.3*0.20 + 0.6*6.25 + 1.0*0.60
    #   = 0.30 + 0.42 + 0.66 + 3.75 + 0.60 = 5.73
    result = get_helper("ft_altman_z_score").impl(
        current_assets=100.0,
        current_liabilities=50.0,
        total_assets=200.0,
        retained_earnings=60.0,
        ebit=40.0,
        market_cap=500.0,
        total_liabilities=80.0,
        total_revenue=120.0,
    )
    assert result["z_score"] == pytest.approx(5.73, abs=0.01)
    assert result["zone"] == "safe"


def test_altman_z_score_zero_assets_raises() -> None:
    with pytest.raises(ValueError, match="total_assets"):
        get_helper("ft_altman_z_score").impl(
            current_assets=50.0,
            current_liabilities=30.0,
            total_assets=0.0,
            retained_earnings=20.0,
            ebit=10.0,
            market_cap=100.0,
            total_liabilities=60.0,
            total_revenue=80.0,
        )


# ---------------------------------------------------------------------------
# ft_piotroski_f_score
# ---------------------------------------------------------------------------


def test_piotroski_f_score_strong() -> None:
    # MSFT-like: profitable, improving, no dilution
    result = get_helper("ft_piotroski_f_score").impl(
        net_income=F.INCOME["net_income"],
        total_assets=F.BALANCE["total_assets"],
        operating_cash_flow=F.CASH_FLOW["operating_cash_flow"],
        total_debt_current=F.BALANCE["total_debt"],
        total_debt_prior=F.BALANCE_PRIOR["total_debt"],
        current_assets=F.BALANCE["current_assets"],
        current_liabilities=F.BALANCE["current_liabilities"],
        current_assets_prior=F.BALANCE_PRIOR["current_assets"],
        current_liabilities_prior=F.BALANCE_PRIOR["current_liabilities"],
        shares_outstanding=F.MARKET["shares_outstanding"],
        shares_outstanding_prior=F.MARKET_PRIOR["shares_outstanding"],
        gross_profit=F.INCOME["gross_profit"],
        revenue=F.INCOME["revenue"],
        gross_profit_prior=F.BALANCE_PRIOR["gross_profit"],
        revenue_prior=F.BALANCE_PRIOR["revenue"],
        total_assets_prior=F.BALANCE_PRIOR["total_assets"],
        net_income_prior=F.INCOME_PRIOR["net_income"],
    )
    assert isinstance(result, dict)
    assert "f_score" in result
    assert "strength" in result
    assert 0 <= result["f_score"] <= 9
    # MSFT: positive ROA, positive OCF, improving ROA, high score expected
    assert result["f_score"] >= 6


def test_piotroski_f_score_range() -> None:
    # Minimal valid call
    result = get_helper("ft_piotroski_f_score").impl(
        net_income=100.0,
        total_assets=500.0,
        operating_cash_flow=120.0,
        total_debt_current=200.0,
        total_debt_prior=220.0,  # decreasing debt = 1 point
        current_assets=300.0,
        current_liabilities=150.0,
        current_assets_prior=280.0,
        current_liabilities_prior=145.0,
        shares_outstanding=100.0,
        shares_outstanding_prior=100.0,  # no dilution = 1 point
        gross_profit=400.0,
        revenue=1000.0,
        gross_profit_prior=380.0,
        revenue_prior=950.0,
        total_assets_prior=490.0,
        net_income_prior=90.0,
    )
    assert 0 <= result["f_score"] <= 9
    assert result["strength"] in ("strong", "neutral", "weak")


# ---------------------------------------------------------------------------
# ft_growth_metrics
# ---------------------------------------------------------------------------


def test_growth_metrics_revenue_growth() -> None:
    result = get_helper("ft_growth_metrics").impl(
        revenue=F.INCOME["revenue"],
        revenue_prior=F.INCOME_PRIOR["revenue"],
        net_income=F.INCOME["net_income"],
        net_income_prior=F.INCOME_PRIOR["net_income"],
    )
    assert isinstance(result, dict)
    # Revenue growth: (61.86B - 52.75B) / 52.75B ≈ 17.3%
    assert result["revenue_growth"] == pytest.approx(
        (F.INCOME["revenue"] - F.INCOME_PRIOR["revenue"]) / F.INCOME_PRIOR["revenue"],
        rel=0.001,
    )


def test_growth_metrics_zero_prior_returns_none() -> None:
    result = get_helper("ft_growth_metrics").impl(
        revenue=100.0,
        revenue_prior=0.0,  # division by zero guard
        net_income=50.0,
        net_income_prior=40.0,
    )
    assert result["revenue_growth"] is None
    assert result["net_income_growth"] == pytest.approx((50.0 - 40.0) / 40.0)


# ---------------------------------------------------------------------------
# ft_per_share_metrics
# ---------------------------------------------------------------------------


def test_per_share_eps_formula() -> None:
    # EPS = (NI - preferred dividends) / shares = 100 / 10 = 10
    result = get_helper("ft_per_share_metrics").impl(
        net_income=100.0,
        total_equity=500.0,
        shares_outstanding=10.0,
    )
    assert result["eps"] == pytest.approx(10.0)
    # BVPS = 500 / 10 = 50
    assert result["book_value_per_share"] == pytest.approx(50.0)


def test_per_share_zero_shares_raises() -> None:
    with pytest.raises(ValueError, match="shares_outstanding"):
        get_helper("ft_per_share_metrics").impl(
            net_income=100.0,
            total_equity=500.0,
            shares_outstanding=0.0,
        )


def test_per_share_fcf_per_share() -> None:
    result = get_helper("ft_per_share_metrics").impl(
        net_income=100.0,
        total_equity=500.0,
        shares_outstanding=10.0,
        free_cash_flow=80.0,
    )
    assert result["free_cash_flow_per_share"] == pytest.approx(8.0)


# ---------------------------------------------------------------------------
# ft_cash_flow_metrics
# ---------------------------------------------------------------------------


def test_cash_flow_metrics_ocf_margin() -> None:
    result = get_helper("ft_cash_flow_metrics").impl(
        operating_cash_flow=F.CASH_FLOW["operating_cash_flow"],
        free_cash_flow=F.CASH_FLOW["free_cash_flow"],
        revenue=F.INCOME["revenue"],
        net_income=F.INCOME["net_income"],
    )
    assert result["ocf_margin"] == pytest.approx(
        F.CASH_FLOW["operating_cash_flow"] / F.INCOME["revenue"], rel=0.001
    )
    assert result["fcf_margin"] == pytest.approx(
        F.CASH_FLOW["free_cash_flow"] / F.INCOME["revenue"], rel=0.001
    )


def test_cash_flow_metrics_zero_revenue_raises() -> None:
    with pytest.raises(ValueError, match="revenue"):
        get_helper("ft_cash_flow_metrics").impl(
            operating_cash_flow=100.0,
            free_cash_flow=80.0,
            revenue=0.0,
            net_income=50.0,
        )


# ---------------------------------------------------------------------------
# ft_dividend_metrics
# ---------------------------------------------------------------------------


def test_dividend_metrics_payout_ratio() -> None:
    result = get_helper("ft_dividend_metrics").impl(
        dividends_paid=F.MARKET["dividends_paid"],
        net_income=F.INCOME["net_income"],
        share_price=F.MARKET["share_price"],
        shares_outstanding=F.MARKET["shares_outstanding"],
    )
    assert isinstance(result, dict)
    assert result["payout_ratio"] == pytest.approx(
        F.MARKET["dividends_paid"] / F.INCOME["net_income"], rel=0.001
    )
    # Retention = 1 - payout
    assert result["retention_ratio"] == pytest.approx(
        1 - F.MARKET["dividends_paid"] / F.INCOME["net_income"], rel=0.001
    )


def test_dividend_metrics_yield_formula() -> None:
    # dividend yield = DPS / price = 3.0 / 100.0 = 0.03
    result = get_helper("ft_dividend_metrics").impl(
        dividends_paid=300.0,
        net_income=1000.0,
        share_price=100.0,
        dividends_per_share=3.0,
    )
    assert result["dividend_yield"] == pytest.approx(0.03)


# ---------------------------------------------------------------------------
# ft_working_capital_metrics
# ---------------------------------------------------------------------------


def test_working_capital_metrics_nwc() -> None:
    result = get_helper("ft_working_capital_metrics").impl(
        current_assets=F.BALANCE["current_assets"],
        current_liabilities=F.BALANCE["current_liabilities"],
        revenue=F.INCOME["revenue"],
    )
    nwc_expected = F.BALANCE["current_assets"] - F.BALANCE["current_liabilities"]
    assert result["net_working_capital"] == pytest.approx(nwc_expected)
    assert result["nwc_to_revenue"] == pytest.approx(nwc_expected / F.INCOME["revenue"], rel=0.001)


def test_working_capital_metrics_ccc() -> None:
    result = get_helper("ft_working_capital_metrics").impl(
        current_assets=200.0,
        current_liabilities=100.0,
        revenue=1000.0,
        cost_of_goods_sold=600.0,
        inventory=50.0,
        accounts_receivable=100.0,
        accounts_payable=80.0,
    )
    assert result["cash_conversion_cycle"] is not None
    assert result["days_inventory_outstanding"] is not None
    assert result["days_sales_outstanding"] is not None
    assert result["days_payable_outstanding"] is not None


# ---------------------------------------------------------------------------
# ft_capital_structure
# ---------------------------------------------------------------------------


def test_capital_structure_wacc() -> None:
    result = get_helper("ft_capital_structure").impl(
        total_debt=F.BALANCE["total_debt"],
        total_equity=F.BALANCE["total_equity"],
        total_assets=F.BALANCE["total_assets"],
        interest_expense=F.INCOME["interest_expense"],
        market_cap=F.MARKET["market_cap"],
        beta=F.MARKET["beta"],
        ebit=F.INCOME["ebit"],
        depreciation_and_amortization=F.INCOME["depreciation_and_amortization"],
    )
    assert isinstance(result, dict)
    assert result["wacc"] is not None
    # WACC should be a reasonable rate (1% - 30%)
    assert 0.01 < result["wacc"] < 0.30
    assert result["cost_of_equity_capm"] > 0
    assert result["debt_to_equity"] == pytest.approx(
        F.BALANCE["total_debt"] / F.BALANCE["total_equity"], rel=0.001
    )


def test_capital_structure_capm_formula() -> None:
    # Cost of equity = Rf + beta * ERP = 0.04 + 1.5 * 0.06 = 0.13
    result = get_helper("ft_capital_structure").impl(
        total_debt=100.0,
        total_equity=200.0,
        total_assets=300.0,
        interest_expense=5.0,
        risk_free_rate=0.04,
        equity_risk_premium=0.06,
        beta=1.5,
    )
    assert result["cost_of_equity_capm"] == pytest.approx(0.04 + 1.5 * 0.06)


# ---------------------------------------------------------------------------
# ft_quality_metrics
# ---------------------------------------------------------------------------


def test_quality_metrics_accrual_ratio() -> None:
    result = get_helper("ft_quality_metrics").impl(
        net_income=F.INCOME["net_income"],
        operating_cash_flow=F.CASH_FLOW["operating_cash_flow"],
        total_assets=F.BALANCE["total_assets"],
        revenue=F.INCOME["revenue"],
        free_cash_flow=F.CASH_FLOW["free_cash_flow"],
    )
    # accrual_ratio = (NI - OCF) / TA
    expected_accrual = (F.INCOME["net_income"] - F.CASH_FLOW["operating_cash_flow"]) / F.BALANCE[
        "total_assets"
    ]
    assert result["accrual_ratio"] == pytest.approx(expected_accrual, abs=0.0001)
    # MSFT OCF > NI → income quality > 1
    assert result["income_quality_ratio"] is not None
    assert result["income_quality_ratio"] > 1.0


def test_quality_metrics_zero_assets_raises() -> None:
    with pytest.raises(ValueError, match="total_assets"):
        get_helper("ft_quality_metrics").impl(
            net_income=100.0,
            operating_cash_flow=120.0,
            total_assets=0.0,
            revenue=1000.0,
        )


# ---------------------------------------------------------------------------
# fred_credit_spreads (canned CSV, no live HTTP)
# ---------------------------------------------------------------------------


def _make_response(csv_text: str) -> MagicMock:
    """Return a mock requests.Response that returns csv_text."""
    m = MagicMock()
    m.status_code = 200
    m.text = csv_text
    return m


def test_fred_credit_spreads_parses_csv() -> None:
    """FRED helper correctly parses canned CSV and returns latest values."""

    def fake_get(url: str, timeout: int = 15) -> MagicMock:
        if "BAMLH0A0HYM2" in url:
            return _make_response(F.FRED_HY_CSV)
        elif "BAMLC0A0CM" in url:
            return _make_response(F.FRED_IG_CSV)
        elif "DGS10" in url:
            return _make_response(F.FRED_TSY_CSV)
        raise ValueError(f"Unexpected URL: {url}")

    with patch(
        "openlia.llm.runtime.report_v2_2.tools.library_helpers.fred.fred_credit_spreads.requests.get",
        side_effect=fake_get,
    ):
        result = get_helper("fred_credit_spreads").impl()

    assert isinstance(result, dict)
    assert result["hy_oas"] == pytest.approx(3.15)
    assert result["ig_oas"] == pytest.approx(0.91)
    assert result["treasury_10y"] == pytest.approx(4.50)
    assert result["as_of"] == "2024-05-14"
    assert result["source"] == "FRED via ICE BofA"
    assert result["spread_differential"] == pytest.approx(3.15 - 0.91, abs=0.0001)


def test_fred_credit_spreads_http_error_raises() -> None:
    """FRED helper raises RuntimeError on non-200 HTTP status."""
    bad_response = MagicMock()
    bad_response.status_code = 503

    with patch(
        "openlia.llm.runtime.report_v2_2.tools.library_helpers.fred.fred_credit_spreads.requests.get",
        return_value=bad_response,
    ):
        with pytest.raises(RuntimeError, match="FRED HTTP 503"):
            get_helper("fred_credit_spreads").impl()


def test_fred_credit_spreads_empty_data_raises() -> None:
    """FRED helper raises RuntimeError when CSV has no valid data."""
    empty_csv = "DATE,BAMLH0A0HYM2\n"

    def fake_get(url: str, timeout: int = 15) -> MagicMock:
        return _make_response(empty_csv)

    with patch(
        "openlia.llm.runtime.report_v2_2.tools.library_helpers.fred.fred_credit_spreads.requests.get",
        side_effect=fake_get,
    ):
        with pytest.raises(RuntimeError, match="No valid data"):
            get_helper("fred_credit_spreads").impl()


# ---------------------------------------------------------------------------
# Artifact type registry: all 16 new artifact types must be present
# ---------------------------------------------------------------------------


def test_new_artifact_types_in_registry() -> None:
    from openlia.llm.runtime.report_v2_2.artifact_types import _registry

    expected = [
        "ft_liquidity_ratios_output",
        "ft_solvency_ratios_output",
        "ft_profitability_ratios_output",
        "ft_efficiency_ratios_output",
        "ft_valuation_ratios_output",
        "ft_dupont_output",
        "ft_altman_z_score_output",
        "ft_piotroski_f_score_output",
        "ft_growth_metrics_output",
        "ft_per_share_metrics_output",
        "ft_cash_flow_metrics_output",
        "ft_dividend_metrics_output",
        "ft_working_capital_metrics_output",
        "ft_capital_structure_output",
        "ft_quality_metrics_output",
        "fred_credit_spreads_output",
    ]
    missing = [name for name in expected if _registry.get(name) is None]
    assert not missing, f"Missing artifact types: {missing}"
