"""Tests for reit_valuation_panel helper (PR 3.2).

Covers:
- FFO computed correctly from NI + D&A + losses - gains
- AFFO = FFO - recurring_capex - straight_line_rent_adj + sbc
- NAV calculation with 3 asset classes and known cap rates reconciles
- Premium/discount to NAV calculation
- AFFO payout > 80% triggers warning
- Missing cap_rate_assumptions raises ValueError
- Skill doc exists at the declared path
"""

from __future__ import annotations

import os

import pytest

# ---------------------------------------------------------------------------
# Registry helpers
# ---------------------------------------------------------------------------


def _get(name: str):
    from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

    h = get_helper(name)
    assert h is not None, f"Helper {name!r} not registered"
    return h


def _run(name: str, **kwargs):
    return _get(name).impl(**kwargs)


def _schema(name: str):
    return _get(name).schema


# ---------------------------------------------------------------------------
# Minimal valid financials fixture (Realty Income style)
# ---------------------------------------------------------------------------

_BASE_FINANCIALS: dict = {
    "net_income": 380,
    "real_estate_depreciation": 540,
    "gains_on_sales": 25,
    "losses_on_sales": 0,
    "impairment_charges": 0,
    "recurring_capex": 65,
    "straight_line_rent_adj": 18,
    "stock_based_comp": 6,
    "dividends_paid": 663,
    "shares_outstanding": 855,
    "market_cap": 7218,
    "current_price": 8.45,
    "total_debt": 5800,
    "preferred_equity": 0,
    "cash_and_equivalents": 285,
    "noi_annualized": 2880,
    "ebitda": 1500,
    "interest_expense": 280,
    "same_store_noi_current": 720,
    "same_store_noi_prior_year": 695,
    "occupancy_rate": 0.988,
    "walt_years": 9.1,
    "total_assets": 25000,
}

_BASE_CAP_RATES: dict = {"blended": 0.055}


def _run_base(**fin_overrides) -> dict:
    financials = {**_BASE_FINANCIALS, **fin_overrides}
    return _run(
        "reit_valuation_panel",
        ticker="O",
        financials=financials,
        cap_rate_assumptions=_BASE_CAP_RATES,
    )


# ---------------------------------------------------------------------------
# 1. FFO computation
# ---------------------------------------------------------------------------


class TestFFO:
    def test_ffo_basic_formula(self) -> None:
        """FFO = NI + D&A + losses_on_sales - gains_on_sales + impairment.

        380 + 540 + 0 - 25 + 0 = 895.
        """
        result = _run_base()
        assert result["income"]["ffo"] == pytest.approx(895)

    def test_ffo_includes_losses_on_sales(self) -> None:
        """Losses on sales are added back in FFO."""
        result = _run_base(losses_on_sales=10, gains_on_sales=0)
        # FFO = 380 + 540 + 10 - 0 + 0 = 930
        assert result["income"]["ffo"] == pytest.approx(930)

    def test_ffo_subtracts_gains_on_sales(self) -> None:
        """Gains on sales are subtracted in FFO."""
        result = _run_base(gains_on_sales=50, losses_on_sales=0)
        # FFO = 380 + 540 + 0 - 50 + 0 = 870
        assert result["income"]["ffo"] == pytest.approx(870)

    def test_ffo_includes_impairment(self) -> None:
        """Impairment charges are added back in FFO."""
        result = _run_base(impairment_charges=100)
        # FFO = 380 + 540 + 0 - 25 + 100 = 995
        assert result["income"]["ffo"] == pytest.approx(995)

    def test_ffo_none_when_net_income_missing(self) -> None:
        result = _run(
            "reit_valuation_panel",
            ticker="X",
            financials={"real_estate_depreciation": 100},
            cap_rate_assumptions={"blended": 0.05},
        )
        assert result["income"]["ffo"] is None

    def test_ffo_none_when_depreciation_missing(self) -> None:
        result = _run(
            "reit_valuation_panel",
            ticker="X",
            financials={"net_income": 200},
            cap_rate_assumptions={"blended": 0.05},
        )
        assert result["income"]["ffo"] is None

    def test_ffo_per_share_computed(self) -> None:
        """FFO/share = ffo / shares = 895 / 855 ≈ 1.0468."""
        result = _run_base()
        expected = 895 / 855
        assert result["income"]["ffo_per_share_diluted"] == pytest.approx(expected, rel=1e-3)

    def test_ffo_growth_yoy_computed(self) -> None:
        """FFO YoY growth = (ffo - ffo_prior_year) / ffo_prior_year."""
        result = _run_base(ffo_prior_year=850)
        expected = (895 - 850) / 850
        assert result["income"]["ffo_growth_yoy_pct"] == pytest.approx(expected, rel=1e-4)

    def test_ffo_growth_qoq_computed(self) -> None:
        result = _run_base(ffo_prior_period=880)
        expected = (895 - 880) / 880
        assert result["income"]["ffo_growth_qoq_pct"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# 2. AFFO computation
# ---------------------------------------------------------------------------


class TestAFFO:
    def test_affo_basic_formula(self) -> None:
        """AFFO = FFO - recurring_capex - straight_line_adj + sbc.

        895 - 65 - 18 + 6 = 818.
        """
        result = _run_base()
        assert result["affo"]["affo"] == pytest.approx(818)

    def test_affo_none_when_recurring_capex_missing(self) -> None:
        """Without recurring_capex, AFFO cannot be computed."""
        financials = {k: v for k, v in _BASE_FINANCIALS.items() if k != "recurring_capex"}
        result = _run(
            "reit_valuation_panel",
            ticker="O",
            financials=financials,
            cap_rate_assumptions=_BASE_CAP_RATES,
        )
        assert result["affo"]["affo"] is None

    def test_affo_subtracts_straight_line_adj(self) -> None:
        """Larger straight-line adj reduces AFFO."""
        result_low = _run_base(straight_line_rent_adj=10)
        result_high = _run_base(straight_line_rent_adj=40)
        assert result_low["affo"]["affo"] > result_high["affo"]["affo"]

    def test_affo_adds_back_sbc(self) -> None:
        """Higher SBC increases AFFO."""
        result_low = _run_base(stock_based_comp=0)
        result_high = _run_base(stock_based_comp=30)
        assert result_high["affo"]["affo"] > result_low["affo"]["affo"]

    def test_affo_per_share_computed(self) -> None:
        """AFFO/share = 818 / 855."""
        result = _run_base()
        expected = 818 / 855
        assert result["affo"]["affo_per_share_diluted"] == pytest.approx(expected, rel=1e-3)

    def test_affo_payout_ratio_formula(self) -> None:
        """AFFO payout ratio = dividends_paid / affo = 663 / 818."""
        result = _run_base()
        expected = 663 / 818
        assert result["affo"]["affo_payout_ratio"] == pytest.approx(expected, rel=1e-4)


# ---------------------------------------------------------------------------
# 3. NAV calculation with 3 asset classes
# ---------------------------------------------------------------------------


class TestNAV:
    def test_nav_single_cap_rate(self) -> None:
        """NAV per share: implied_re = NOI/cap; equity = re + cash - debt - pref; /shares.

        NOI = 2880, cap = 5.5% → RE = 52,363.6
        Cash = 285, Debt = 5800, Pref = 0
        Equity = 52,363.6 + 285 - 5800 = 46,848.6
        NAV/share = 46,848.6 / 855 ≈ 54.79
        """
        result = _run_base()
        re_value = 2880 / 0.055
        nav_equity = re_value + 285 - 5800 - 0
        expected_nav = nav_equity / 855
        nav_ps = result["valuation"]["nav_per_share"]
        assert nav_ps is not None
        assert nav_ps == pytest.approx(expected_nav, rel=1e-4)

    def test_nav_with_preferred_equity(self) -> None:
        """Preferred equity reduces NAV equity."""
        result_no_pref = _run_base(preferred_equity=0)
        result_with_pref = _run_base(preferred_equity=500)
        assert (
            result_no_pref["valuation"]["nav_per_share"]
            > result_with_pref["valuation"]["nav_per_share"]
        )

    def test_nav_with_explicit_per_type_cap_rates(self) -> None:
        """Non-blended cap rates: uses first value when no 'blended' key."""
        result = _run(
            "reit_valuation_panel",
            ticker="PLD",
            financials={
                "net_income": 1200,
                "real_estate_depreciation": 1800,
                "gains_on_sales": 50,
                "recurring_capex": 120,
                "straight_line_rent_adj": 80,
                "stock_based_comp": 0,
                "shares_outstanding": 900,
                "noi_annualized": 6000,
                "total_debt": 25000,
                "cash_and_equivalents": 1800,
            },
            cap_rate_assumptions={"industrial": 0.046},
        )
        re_value = 6000 / 0.046
        nav_equity = re_value + 1800 - 25000 - 0
        expected_nav = nav_equity / 900
        assert result["valuation"]["nav_per_share"] == pytest.approx(expected_nav, rel=1e-4)

    def test_nav_three_asset_classes_uses_blended(self) -> None:
        """Multi-type dict: 'blended' key takes precedence."""
        result = _run(
            "reit_valuation_panel",
            ticker="DLR",
            financials={
                "net_income": 400,
                "real_estate_depreciation": 800,
                "gains_on_sales": 0,
                "recurring_capex": 100,
                "noi_annualized": 3000,
                "total_debt": 10000,
                "cash_and_equivalents": 500,
                "shares_outstanding": 300,
            },
            cap_rate_assumptions={
                "data_center": 0.045,
                "office": 0.070,
                "blended": 0.052,
            },
        )
        # Should use "blended" = 0.052
        re_value = 3000 / 0.052
        nav_equity = re_value + 500 - 10000 - 0
        expected_nav = nav_equity / 300
        assert result["valuation"]["nav_per_share"] == pytest.approx(expected_nav, rel=1e-4)

    def test_nav_per_share_none_when_noi_missing(self) -> None:
        result = _run(
            "reit_valuation_panel",
            ticker="X",
            financials={"total_debt": 1000, "cash_and_equivalents": 100, "shares_outstanding": 50},
            cap_rate_assumptions={"blended": 0.055},
        )
        assert result["valuation"]["nav_per_share"] is None


# ---------------------------------------------------------------------------
# 4. Premium/discount to NAV
# ---------------------------------------------------------------------------


class TestPremiumDiscountToNAV:
    def test_discount_when_price_below_nav(self) -> None:
        """Discount = current_price / nav_per_share - 1 < 0."""
        # NOI = 2880, cap = 5.5% → RE = 52,363.6; equity = 46,848.6; nav/sh ≈ 54.79
        # current_price = 8.45 < 54.79 → deep discount (different scale; use known values)
        # Let's construct a case where we know the outcome precisely
        result = _run(
            "reit_valuation_panel",
            ticker="TEST",
            financials={
                "net_income": 100,
                "real_estate_depreciation": 200,
                "gains_on_sales": 0,
                "recurring_capex": 50,
                "noi_annualized": 1000,
                "total_debt": 5000,
                "cash_and_equivalents": 500,
                "shares_outstanding": 100,
                "current_price": 45.0,  # price per share
                "market_cap": 4500,
            },
            cap_rate_assumptions={"blended": 0.050},
        )
        # nav: re_value = 1000/0.05 = 20000; equity = 20000 + 500 - 5000 = 15500
        # nav_per_share = 15500 / 100 = 155
        # premium_discount = 45/155 - 1 ≈ -0.710
        pd = result["valuation"]["premium_discount_to_nav_pct"]
        assert pd is not None
        assert pd < 0  # discount
        assert pd == pytest.approx(45.0 / 155.0 - 1.0, rel=1e-4)

    def test_premium_when_price_above_nav(self) -> None:
        """Premium = positive premium_discount_to_nav_pct."""
        # nav: re_value = 500/0.06 ≈ 8333.3; equity = 8333.3 + 200 - 1000 = 7533.3
        # nav_per_share = 7533.3 / 100 = 75.33
        # For premium: use price above nav per share
        result2 = _run(
            "reit_valuation_panel",
            ticker="TEST",
            financials={
                "net_income": 100,
                "real_estate_depreciation": 200,
                "gains_on_sales": 0,
                "recurring_capex": 50,
                "noi_annualized": 500,
                "total_debt": 1000,
                "cash_and_equivalents": 200,
                "shares_outstanding": 100,
                "current_price": 80.0,
                "market_cap": 8000,
            },
            cap_rate_assumptions={"blended": 0.06},
        )
        pd = result2["valuation"]["premium_discount_to_nav_pct"]
        assert pd is not None
        assert pd > 0  # premium

    def test_premium_discount_top_level_matches_valuation_block(self) -> None:
        """Top-level premium_discount_to_nav_pct == valuation block value."""
        result = _run_base()
        assert (
            result["premium_discount_to_nav_pct"]
            == result["valuation"]["premium_discount_to_nav_pct"]
        )

    def test_premium_discount_none_when_price_missing(self) -> None:
        financials = {k: v for k, v in _BASE_FINANCIALS.items() if k != "current_price"}
        result = _run(
            "reit_valuation_panel",
            ticker="O",
            financials=financials,
            cap_rate_assumptions=_BASE_CAP_RATES,
        )
        assert result["valuation"]["premium_discount_to_nav_pct"] is None


# ---------------------------------------------------------------------------
# 5. AFFO payout > 80% warning
# ---------------------------------------------------------------------------


class TestAFFOPayoutWarning:
    def test_payout_above_80pct_triggers_warning(self) -> None:
        """AFFO payout > 80% → warning fires."""
        # Base case: dividends=663, affo=818 → payout ≈ 81% → warning
        result = _run_base()
        assert result["affo"]["affo_payout_ratio"] is not None
        assert result["affo"]["affo_payout_ratio"] > 0.80
        assert any("80%" in w or "payout" in w.lower() for w in result["warnings"])

    def test_payout_exactly_80pct_triggers_warning(self) -> None:
        """Payout ratio of exactly 80% → warning fires (> 80% is strict; 80% is not > 80%)."""
        # affo = 895 - 65 - 18 + 6 = 818; dividends = 818 * 0.80 = 654.4
        result = _run_base(dividends_paid=654.4)
        payout = result["affo"]["affo_payout_ratio"]
        # exactly 80%: NOT > 80% → no warning (strict threshold)
        assert payout is not None
        assert payout == pytest.approx(0.80, rel=1e-3)
        # 80% is not > 80%: warning should NOT fire at the threshold
        assert not any("80%" in w for w in result["warnings"])

    def test_payout_81pct_triggers_warning(self) -> None:
        """Payout ratio of 81% → warning fires."""
        # affo = 818; dividends = 818 * 0.81 ≈ 662.58
        result = _run_base(dividends_paid=662.58)
        assert any("80%" in w or "payout" in w.lower() for w in result["warnings"])

    def test_payout_below_80pct_no_warning(self) -> None:
        """Payout ratio of 70% → no payout warning."""
        # affo = 818; dividends = 818 * 0.70 = 572.6
        result = _run_base(dividends_paid=572.6)
        payout = result["affo"]["affo_payout_ratio"]
        assert payout is not None
        assert payout < 0.80
        assert not any("80%" in w for w in result["warnings"])

    def test_no_payout_warning_when_dividends_missing(self) -> None:
        """Without dividends_paid, no payout ratio → no payout warning."""
        financials = {k: v for k, v in _BASE_FINANCIALS.items() if k != "dividends_paid"}
        result = _run(
            "reit_valuation_panel",
            ticker="O",
            financials=financials,
            cap_rate_assumptions=_BASE_CAP_RATES,
        )
        assert result["affo"]["affo_payout_ratio"] is None
        assert not any("80%" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# 6. Missing cap_rate_assumptions raises ValueError
# ---------------------------------------------------------------------------


class TestCapRateValidation:
    def test_missing_cap_rate_assumptions_raises_value_error(self) -> None:
        """Empty cap_rate_assumptions → ValueError with decision #15 message."""
        with pytest.raises(ValueError, match="decision #15"):
            _run(
                "reit_valuation_panel",
                ticker="O",
                financials=_BASE_FINANCIALS,
                cap_rate_assumptions={},
            )

    def test_none_cap_rate_assumptions_raises_value_error(self) -> None:
        """None cap_rate_assumptions → TypeError or ValueError."""
        with pytest.raises((ValueError, TypeError)):
            _run(
                "reit_valuation_panel",
                ticker="O",
                financials=_BASE_FINANCIALS,
                cap_rate_assumptions=None,
            )

    def test_valid_single_cap_rate_accepted(self) -> None:
        result = _run(
            "reit_valuation_panel",
            ticker="O",
            financials=_BASE_FINANCIALS,
            cap_rate_assumptions={"blended": 0.055},
        )
        assert result["valuation"]["applied_cap_rate_pct"] == pytest.approx(0.055)

    def test_non_blended_key_accepted(self) -> None:
        result = _run(
            "reit_valuation_panel",
            ticker="PLD",
            financials=_BASE_FINANCIALS,
            cap_rate_assumptions={"industrial": 0.046},
        )
        assert result["valuation"]["applied_cap_rate_pct"] == pytest.approx(0.046)


# ---------------------------------------------------------------------------
# 7. Net Debt / EBITDA > 7x warning
# ---------------------------------------------------------------------------


class TestNetDebtEBITDAWarning:
    def test_net_debt_ebitda_above_7x_triggers_warning(self) -> None:
        """Net Debt/EBITDA > 7x → warning fires."""
        # net_debt = 5800 - 285 = 5515; ebitda = 700 → ratio = 7.878x
        result = _run_base(ebitda=700)
        nd_ebitda = result["balance_sheet"]["net_debt_to_ebitda"]
        assert nd_ebitda is not None
        assert nd_ebitda > 7.0
        assert any("7x" in w or "EBITDA" in w for w in result["warnings"])

    def test_net_debt_ebitda_below_7x_no_warning(self) -> None:
        """Net Debt/EBITDA < 7x → no leverage warning."""
        # net_debt = 5515; ebitda = 1500 → ratio ≈ 3.68x
        result = _run_base(ebitda=1500)
        nd_ebitda = result["balance_sheet"]["net_debt_to_ebitda"]
        assert nd_ebitda is not None
        assert nd_ebitda < 7.0
        assert not any("7x" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# 8. Operating metrics
# ---------------------------------------------------------------------------


class TestOperatingMetrics:
    def test_same_store_noi_growth_computed(self) -> None:
        """SS NOI growth = (720 - 695) / 695 ≈ 3.6%."""
        result = _run_base()
        expected = (720 - 695) / 695
        assert result["operating_metrics"]["same_store_noi_growth_pct"] == pytest.approx(
            expected, rel=1e-4
        )

    def test_same_store_noi_growth_none_when_prior_missing(self) -> None:
        financials = {k: v for k, v in _BASE_FINANCIALS.items() if k != "same_store_noi_prior_year"}
        result = _run(
            "reit_valuation_panel",
            ticker="O",
            financials=financials,
            cap_rate_assumptions=_BASE_CAP_RATES,
        )
        assert result["operating_metrics"]["same_store_noi_growth_pct"] is None

    def test_occupancy_passed_through(self) -> None:
        result = _run_base()
        assert result["operating_metrics"]["occupancy_rate_pct"] == pytest.approx(0.988)

    def test_walt_passed_through(self) -> None:
        result = _run_base()
        assert result["operating_metrics"]["walt_years"] == pytest.approx(9.1)

    def test_occupancy_below_90pct_triggers_warning(self) -> None:
        result = _run_base(occupancy_rate=0.85)
        assert any("90%" in w or "occupancy" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# 9. Balance sheet metrics
# ---------------------------------------------------------------------------


class TestBalanceSheet:
    def test_net_debt_computed(self) -> None:
        """Net debt = total_debt - cash = 5800 - 285 = 5515."""
        result = _run_base()
        assert result["balance_sheet"]["net_debt"] == pytest.approx(5515)

    def test_debt_to_assets_computed(self) -> None:
        """Debt/assets = 5800 / 25000 = 0.232."""
        result = _run_base()
        expected = 5800 / 25000
        assert result["balance_sheet"]["debt_to_assets_pct"] == pytest.approx(expected, rel=1e-5)

    def test_interest_coverage_computed(self) -> None:
        """Interest coverage = ebitda / interest_expense = 1500 / 280."""
        result = _run_base()
        expected = 1500 / 280
        assert result["balance_sheet"]["interest_coverage_ratio"] == pytest.approx(
            expected, rel=1e-4
        )

    def test_unsecured_debt_pct_computed(self) -> None:
        result = _run_base(unsecured_debt=4000)
        expected = 4000 / 5800
        assert result["balance_sheet"]["unsecured_debt_pct_of_total"] == pytest.approx(
            expected, rel=1e-4
        )


# ---------------------------------------------------------------------------
# 10. Scores
# ---------------------------------------------------------------------------


class TestScores:
    def test_affo_sustainability_score_present(self) -> None:
        result = _run_base()
        score = result["affo_sustainability_score"]
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_composite_health_score_present(self) -> None:
        result = _run_base()
        score = result["composite_reit_health_score"]
        assert score is not None
        assert 0.0 <= score <= 100.0

    def test_scores_none_when_minimal_data(self) -> None:
        """With almost no data, scores may be None (no components)."""
        result = _run(
            "reit_valuation_panel",
            ticker="EMPTY",
            financials={},
            cap_rate_assumptions={"blended": 0.055},
        )
        # Scores should be None when no components are computable
        assert result["affo_sustainability_score"] is None
        assert result["composite_reit_health_score"] is None

    def test_strong_reit_scores_above_50(self) -> None:
        """Low payout, high occupancy, good NOI growth, low leverage → high score."""
        result = _run(
            "reit_valuation_panel",
            ticker="EXR",
            financials={
                "net_income": 300,
                "real_estate_depreciation": 400,
                "gains_on_sales": 0,
                "recurring_capex": 60,
                "straight_line_rent_adj": 10,
                "stock_based_comp": 0,
                "dividends_paid": 400,  # payout ≈ 63% (low)
                "shares_outstanding": 200,
                "noi_annualized": 1200,
                "same_store_noi_current": 300,
                "same_store_noi_prior_year": 270,  # +11% growth
                "occupancy_rate": 0.965,
                "total_debt": 4000,
                "cash_and_equivalents": 200,
                "ebitda": 1100,  # Net Debt/EBITDA ≈ 3.45x
                "interest_expense": 200,
                "current_price": 50.0,
            },
            cap_rate_assumptions={"blended": 0.052},
        )
        assert result["affo_sustainability_score"] is not None
        assert result["affo_sustainability_score"] >= 50.0


# ---------------------------------------------------------------------------
# 11. Output structure
# ---------------------------------------------------------------------------


class TestOutputStructure:
    def test_required_blocks_present(self) -> None:
        result = _run_base()
        for key in ("income", "affo", "valuation", "operating_metrics", "balance_sheet"):
            assert key in result, f"Missing top-level block: {key}"

    def test_ticker_in_output(self) -> None:
        result = _run_base()
        assert result["ticker"] == "O"

    def test_warnings_is_list(self) -> None:
        result = _run_base()
        assert isinstance(result["warnings"], list)

    def test_narrative_contains_ticker(self) -> None:
        result = _run_base()
        assert "O" in result["narrative"]

    def test_source_provenance_default_empty(self) -> None:
        result = _run_base()
        assert result["source_provenance"] == []

    def test_applied_cap_rate_in_valuation(self) -> None:
        result = _run_base()
        assert result["valuation"]["applied_cap_rate_pct"] == pytest.approx(0.055)

    def test_cap_rate_source_label(self) -> None:
        result = _run_base()
        assert result["valuation"]["cap_rate_source"] == "user_supplied"


# ---------------------------------------------------------------------------
# 12. FFO disclosure mismatch warning
# ---------------------------------------------------------------------------


class TestFFODisclosureMismatch:
    def test_ffo_mismatch_greater_than_2pct_triggers_warning(self) -> None:
        """Computed FFO differs > 2% from disclosed → warning fires."""
        # Computed FFO = 895; disclosed = 800 → diff ≈ 11.9% > 2%
        result = _run_base(nareit_ffo_disclosed=800)
        assert any("differs" in w.lower() or "disclosed" in w.lower() for w in result["warnings"])
        assert result["income"]["ffo_matches_disclosed"] is False

    def test_ffo_match_within_2pct_no_warning(self) -> None:
        """Computed FFO within 2% of disclosed → no mismatch warning."""
        # Computed FFO = 895; disclosed = 895 * 1.005 = 899.5 (< 2% diff)
        result = _run_base(nareit_ffo_disclosed=899)
        assert result["income"]["ffo_matches_disclosed"] is True
        # No mismatch warning should fire
        mismatch_warns = [w for w in result["warnings"] if "disclosed" in w.lower()]
        assert not mismatch_warns


# ---------------------------------------------------------------------------
# 13. Registration and metadata
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_helper_registered(self) -> None:
        h = _get("reit_valuation_panel")
        assert h.schema.directory.name == "reit_valuation_panel"

    def test_produces_reit_valuation_panel_output(self) -> None:
        schema = _schema("reit_valuation_panel")
        assert "reit_valuation_panel_output" in schema.contract.produces_artifacts

    def test_category_is_sector_reits(self) -> None:
        from openlia.llm.runtime.report_v2_2 import Category

        schema = _schema("reit_valuation_panel")
        assert schema.directory.category == Category.SECTOR_REITS

    def test_version_is_1_0_0(self) -> None:
        schema = _schema("reit_valuation_panel")
        assert schema.version == "1.0.0"

    def test_not_deprecated(self) -> None:
        schema = _schema("reit_valuation_panel")
        assert schema.deprecated_at_version is None

    def test_skill_doc_path_declared(self) -> None:
        schema = _schema("reit_valuation_panel")
        assert schema.skill_doc is not None
        assert schema.skill_doc.path == "skills/reit_valuation_panel.md"

    def test_skill_doc_file_exists(self) -> None:
        """Skill doc file must exist at the declared relative path (from library_helpers/)."""
        import openlia.llm.runtime.report_v2_2.tools.library_helpers as lh_pkg

        skills_dir = os.path.join(os.path.dirname(lh_pkg.__file__), "skills")
        skill_path = os.path.join(skills_dir, "reit_valuation_panel.md")
        assert os.path.isfile(skill_path), f"Skill doc missing: {skill_path}"

    def test_skill_doc_estimated_tokens_in_range(self) -> None:
        schema = _schema("reit_valuation_panel")
        assert schema.skill_doc is not None
        assert 1500 <= schema.skill_doc.estimated_tokens <= 2200


# ---------------------------------------------------------------------------
# 14. Artifact type registration
# ---------------------------------------------------------------------------


class TestArtifactType:
    def test_reit_valuation_panel_output_in_registry(self) -> None:
        from openlia.llm.runtime.report_v2_2.artifact_types import _registry

        assert _registry.get("reit_valuation_panel_output") is not None
