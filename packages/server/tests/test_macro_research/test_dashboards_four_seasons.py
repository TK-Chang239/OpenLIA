from __future__ import annotations

import pytest

from openlia.macro_research.dashboards.four_seasons import FourSeasonsDashboard


@pytest.fixture
def d() -> FourSeasonsDashboard:
    return FourSeasonsDashboard()


def test_metadata(d: FourSeasonsDashboard) -> None:
    assert d.slug == "four_seasons"
    assert d.display_name == "Four Seasons"
    assert d.T4_PROMPT_KEY == "four_seasons"


def test_requirements(d: FourSeasonsDashboard) -> None:
    assert "macro_indicator:pmi" in d.T1_REQUIREMENTS
    assert "macro_indicator:gdp_yoy" in d.T1_REQUIREMENTS
    assert "macro_indicator:cpi_yoy" in d.T1_REQUIREMENTS
    assert "stock_quote:HYG" in d.T1_REQUIREMENTS


@pytest.mark.parametrize(
    ("metrics", "season"),
    [
        ({"pmi": 55, "gdp_yoy": 2.5, "cpi_yoy": 1.5, "credit_spread": 0.02}, "Spring"),
        ({"pmi": 55, "gdp_yoy": 2.5, "cpi_yoy": 4.5, "credit_spread": 0.03}, "Summer"),
        ({"pmi": 47, "gdp_yoy": 0.5, "cpi_yoy": 4.5, "credit_spread": 0.06}, "Autumn"),
        ({"pmi": 47, "gdp_yoy": -0.5, "cpi_yoy": 1.2, "credit_spread": 0.08}, "Winter"),
    ],
)
def test_t3_classifies_season(
    d: FourSeasonsDashboard, metrics: dict[str, float], season: str
) -> None:
    out = d.T3_compute(metrics=metrics, portfolio=None)
    assert out["season"] == season


def test_t3_transition_label_when_ambiguous(d: FourSeasonsDashboard) -> None:
    out = d.T3_compute(
        metrics={"pmi": 50.0, "gdp_yoy": 0.0, "cpi_yoy": 2.5, "credit_spread": 0.04},
        portfolio=None,
    )
    assert out["confidence"] in ("mixed", "transitioning")


def test_t5_smart_mode_widens_spread_thresholds() -> None:
    d = FourSeasonsDashboard()
    base = {"credit_spread_warn": 0.04}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "vol_regime": "high"},
    )
    assert out["credit_spread_warn"] > 0.04
