from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.debt_cycle import DebtCycleDashboard


@pytest.fixture
def d() -> DebtCycleDashboard:
    return DebtCycleDashboard()


def test_metadata(d: DebtCycleDashboard) -> None:
    assert d.slug == "debt_cycle"
    assert d.display_name == "Debt Cycle"
    assert d.T4_PROMPT_KEY == "debt_cycle"


def test_t1_requirements_present(d: DebtCycleDashboard) -> None:
    assert "macro_indicator:debt_gdp" in d.T1_REQUIREMENTS
    assert "macro_indicator:interest_revenue" in d.T1_REQUIREMENTS
    assert "stock_quote:TIP" in d.T1_REQUIREMENTS
    assert "stock_quote:UUP" in d.T1_REQUIREMENTS


def test_t2_formulas_match_indicators(d: DebtCycleDashboard) -> None:
    assert "debt_gdp" in d.T2_FORMULAS
    assert "interest_revenue" in d.T2_FORMULAS
    assert "tips_yield" in d.T2_FORMULAS
    assert "dxy" in d.T2_FORMULAS


def test_t3_classifies_expansion() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 60.0, "interest_revenue": 5.0, "tips_yield": 1.8, "dxy": 104.0},
        portfolio=None,
    )
    assert out["phase"] == "Expansion"
    assert out["severity"] == "green"


def test_t3_classifies_late_plateau() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 115.0, "interest_revenue": 14.0, "tips_yield": 0.3, "dxy": 101.0},
        portfolio=None,
    )
    assert out["phase"] in ("Late Plateau", "Plateau")
    assert out["severity"] in ("amber", "red")


def test_t3_classifies_deleveraging() -> None:
    d = DebtCycleDashboard()
    out = d.T3_compute(
        metrics={"debt_gdp": 130.0, "interest_revenue": 22.0, "tips_yield": -0.8, "dxy": 95.0},
        portfolio=None,
    )
    assert out["phase"] == "Deleveraging"
    assert out["severity"] == "red"


def test_t5_smart_mode_tightens_thresholds_in_stress() -> None:
    d = DebtCycleDashboard()
    base = {"debt_gdp_warn": 100.0, "interest_revenue_warn": 15.0}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "recent_spread_widening": True},
    )
    assert out["debt_gdp_warn"] < 100.0
    assert out["interest_revenue_warn"] < 15.0
