from __future__ import annotations

import pytest
from openlia.macro_research.risk_math import (
    coverage_for_season,
    risk_contributions,
)


def test_risk_contributions_sum_to_one() -> None:
    weights = {"equities": 0.6, "bonds": 0.4}
    vols = {"equities": 0.165, "bonds": 0.07}
    out = risk_contributions(weights=weights, vols=vols)
    assert pytest.approx(sum(out.values()), rel=1e-6) == 1.0
    assert out["equities"] > out["bonds"]


def test_risk_contributions_handles_zero_weight() -> None:
    out = risk_contributions(
        weights={"equities": 0.0, "gold": 1.0},
        vols={"equities": 0.165, "gold": 0.16},
    )
    assert out["equities"] == 0.0
    assert out["gold"] == pytest.approx(1.0)


def test_coverage_strong_when_gte_20pct() -> None:
    out = coverage_for_season(
        season="Autumn",
        weights={"gold": 0.15, "commodities": 0.10, "equities": 0.5, "long_bonds": 0.25},
    )
    assert out == "strong"


def test_coverage_exposed_when_zero() -> None:
    out = coverage_for_season(
        season="Autumn",
        weights={"equities": 1.0},
    )
    assert out == "exposed"
