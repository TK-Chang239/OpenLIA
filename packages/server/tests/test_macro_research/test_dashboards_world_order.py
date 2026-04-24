from __future__ import annotations

from openlia.macro_research.dashboards.world_order import WorldOrderDashboard


def test_metadata() -> None:
    d = WorldOrderDashboard()
    assert d.slug == "world_order"
    assert d.T4_PROMPT_KEY == "world_order"


def test_requirements_include_reserves_and_news() -> None:
    d = WorldOrderDashboard()
    assert "macro_indicator:usd_fx_reserve_share" in d.T1_REQUIREMENTS
    assert "macro_indicator:cb_gold_purchases" in d.T1_REQUIREMENTS
    assert "company_news:geopolitical" in d.T1_REQUIREMENTS


def test_t3_wealth_shift_median() -> None:
    d = WorldOrderDashboard()
    out = d.T3_compute(
        metrics={
            "institutional_shift": 3,
            "market_shift": 2,
            "geopolitical_shift": 3,
            "retail_shift": 1,
        },
        portfolio=None,
    )
    assert out["wealth_shift_stage"] in ("mid", "late")


def test_t5_recalibrates_anchors_in_stress() -> None:
    d = WorldOrderDashboard()
    base = {"stage_5_threshold": 0.7}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "dollar_weakness": True},
    )
    assert out["stage_5_threshold"] < 0.7
