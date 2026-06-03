"""Deterministic All-Weather Monte-Carlo stress simulator. Pure; no I/O, no LLM."""

import pytest
from openlia.macro_research.quant.monte_carlo import (
    SCENARIOS,
    simulate_all_weather_stress,
)

_BALANCED = {
    "equities": 0.30,
    "long_bonds": 0.40,
    "intermediate_bonds": 0.15,
    "gold": 0.075,
    "commodities": 0.075,
}


def test_returns_base_plus_three_scenarios() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    names = [s.name for s in out.scenarios]
    assert names[0] == "Base case"
    assert {"Stagflation", "Rate shock", "Equity crash / deleveraging"} <= set(names)
    assert len(out.scenarios) == len(SCENARIOS)


def test_is_deterministic_for_same_weights() -> None:
    a = simulate_all_weather_stress(_BALANCED)
    b = simulate_all_weather_stress(_BALANCED)
    assert a == b


def test_base_distribution_percentiles_are_ordered() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    p = out.distribution.percentiles
    assert p["p5"] < p["p25"] < p["p50"] < p["p75"] < p["p95"]


def test_equity_crash_is_worse_than_base_for_the_user() -> None:
    out = simulate_all_weather_stress(_BALANCED)
    by_name = {s.name: s for s in out.scenarios}
    assert by_name["Equity crash / deleveraging"].user.p5 < by_name["Base case"].user.p5


def test_concentrated_equities_crash_worse_than_reference() -> None:
    out = simulate_all_weather_stress({"equities": 1.0})
    crash = next(s for s in out.scenarios if s.name == "Equity crash / deleveraging")
    # An all-equity book has a deeper crash tail than the diversified reference.
    assert crash.user.p5 < crash.reference.p5


def test_tone_is_derived_from_user_p5() -> None:
    out = simulate_all_weather_stress({"equities": 1.0})
    crash = next(s for s in out.scenarios if s.name == "Equity crash / deleveraging")
    assert crash.tone == "red"


def test_weights_renormalize() -> None:
    a = simulate_all_weather_stress({"equities": 60.0, "long_bonds": 40.0})
    b = simulate_all_weather_stress({"equities": 0.6, "long_bonds": 0.4})
    assert a == b


def test_unknown_asset_raises() -> None:
    with pytest.raises(ValueError, match="unknown asset classes"):
        simulate_all_weather_stress({"crypto": 1.0})


def test_empty_weights_raises() -> None:
    with pytest.raises(ValueError):
        simulate_all_weather_stress({})
