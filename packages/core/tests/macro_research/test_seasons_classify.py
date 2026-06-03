"""Deterministic four_seasons classifier tests.

Parallels test_classification.py / test_world_order_classify.py: pure
thresholds ported from the legacy FourSeasonsDashboard.T3_compute, plus a
deterministic marker placement. No I/O, no LLM.
"""

from openlia.macro_research.quant.seasons import (
    SeasonsInputs,
    classify_four_seasons,
)


def test_spring_growth_rising_inflation_falling():
    out = classify_four_seasons(
        SeasonsInputs(pmi=54.0, gdp_yoy=2.5, cpi_yoy=1.8, credit_spread=0.03)
    )
    assert out.season == "Spring"
    assert out.severity == "green"
    assert out.confidence == "clear"
    assert out.growth_axis == "rising"
    assert out.inflation_axis == "falling"


def test_autumn_growth_falling_inflation_rising():
    out = classify_four_seasons(
        SeasonsInputs(pmi=47.0, gdp_yoy=0.2, cpi_yoy=4.0, credit_spread=0.06)
    )
    assert out.season == "Autumn"
    assert out.severity == "red"
    assert out.growth_axis == "falling"
    assert out.inflation_axis == "rising"


def test_mixed_signals_transitioning():
    # Growth ambiguous (gdp > 1 but pmi < 50) and inflation steady -> not a
    # clean quadrant -> Transitioning, confidence "transitioning".
    out = classify_four_seasons(
        SeasonsInputs(pmi=48.0, gdp_yoy=1.5, cpi_yoy=2.5, credit_spread=0.04)
    )
    assert out.season == "Transitioning"
    assert out.severity == "amber"
    assert out.confidence == "transitioning"
    assert out.growth_axis == "flat"
    assert out.inflation_axis == "steady"


def test_marker_placement_within_bounds():
    out = classify_four_seasons(
        SeasonsInputs(pmi=52.7, gdp_yoy=0.5, cpi_yoy=3.3, credit_spread=0.029)
    )
    assert 0 <= out.marker_x_pct <= 100
    assert 0 <= out.marker_y_pct <= 100


def test_marker_placement_extremes_clamped():
    high = classify_four_seasons(
        SeasonsInputs(pmi=60.0, gdp_yoy=3.0, cpi_yoy=6.0, credit_spread=0.03)
    )
    assert high.marker_x_pct == 100
    assert high.marker_y_pct == 100

    low = classify_four_seasons(
        SeasonsInputs(pmi=40.0, gdp_yoy=0.0, cpi_yoy=0.5, credit_spread=0.03)
    )
    assert low.marker_x_pct == 0
    assert low.marker_y_pct == 0


def test_playbook_assets_present_for_clean_season():
    out = classify_four_seasons(
        SeasonsInputs(pmi=54.0, gdp_yoy=2.5, cpi_yoy=1.8, credit_spread=0.03)
    )
    assert out.best_assets == ["equities"]
    assert out.worst_assets == ["commodities"]
