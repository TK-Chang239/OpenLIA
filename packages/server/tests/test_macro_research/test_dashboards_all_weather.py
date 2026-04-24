from __future__ import annotations

from openlia.macro_research.dashboards.all_weather import AllWeatherDashboard


def test_metadata() -> None:
    d = AllWeatherDashboard()
    assert d.slug == "all_weather"
    assert d.T4_PROMPT_KEY is None


def test_t3_compares_to_reference() -> None:
    d = AllWeatherDashboard()
    user_portfolio = {"equities": 0.6, "long_bonds": 0.35, "gold": 0.05}
    out = d.T3_compute(metrics={}, portfolio=user_portfolio)
    assert "reference_allocation" in out
    assert out["reference_allocation"]["equities"] == 0.30
    assert "risk_contributions" in out
    assert "season_coverage" in out
    assert "gold_gap" in out


def test_t3_falls_back_to_60_40_when_no_portfolio() -> None:
    d = AllWeatherDashboard()
    out = d.T3_compute(metrics={}, portfolio=None)
    assert out["portfolio_source"] == "fallback_60_40"
    assert out["portfolio"]["equities"] == 0.60


def test_t3_flags_red_severity_when_concentration_high() -> None:
    d = AllWeatherDashboard()
    out = d.T3_compute(
        metrics={},
        portfolio={"equities": 1.0, "long_bonds": 0.0, "gold": 0.0},
    )
    assert out["severity"] == "red"
