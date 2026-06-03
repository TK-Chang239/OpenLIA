"""Deterministic all_weather classifier tests.

Wraps risk_math (risk_contributions, coverage_for_season, gold_gap) into a
portfolio-audit classification. Pure function; no I/O, no LLM.
"""

import math

from openlia.macro_research.quant.all_weather import classify_all_weather


def test_concentrated_portfolio_is_red() -> None:
    out = classify_all_weather({"equities": 0.9, "long_bonds": 0.1})
    assert out.severity == "red"
    assert out.overall_coverage_label == "Concentrated"


def test_balanced_reference_is_green() -> None:
    out = classify_all_weather(
        {
            "equities": 0.30,
            "long_bonds": 0.40,
            "intermediate_bonds": 0.15,
            "gold": 0.075,
            "commodities": 0.075,
        }
    )
    assert out.severity == "green"
    assert out.overall_coverage_label == "Balanced"


def test_risk_contributions_sum_to_one() -> None:
    out = classify_all_weather({"equities": 0.6, "long_bonds": 0.4})
    assert math.isclose(sum(out.risk_contributions.values()), 1.0, abs_tol=1e-9)
    assert math.isclose(sum(out.reference_risk_contributions.values()), 1.0, abs_tol=1e-9)


def test_season_coverage_has_four_seasons() -> None:
    out = classify_all_weather({"equities": 0.6, "long_bonds": 0.4})
    assert set(out.season_coverage) == {"Spring", "Summer", "Autumn", "Winter"}


def test_gold_gap_shape() -> None:
    out = classify_all_weather({"equities": 0.6, "long_bonds": 0.4})
    assert set(out.gold_gap) == {"current", "target", "gap"}
    assert out.gold_gap["current"] == 0.0
