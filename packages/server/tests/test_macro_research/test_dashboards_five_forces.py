from __future__ import annotations

import pytest
from openlia.macro_research.dashboards.five_forces import FiveForcesDashboard


def test_metadata() -> None:
    d = FiveForcesDashboard()
    assert d.slug == "five_forces"
    assert d.T4_PROMPT_KEY == "five_forces"


@pytest.mark.parametrize(
    ("scores", "expected_count", "expected_bucket"),
    [
        ([3, 4, 4, 3, 2], 0, "Normal"),
        ([7, 5, 3, 4, 6], 1, "Normal"),
        ([8, 7, 6, 5, 4], 2, "Elevated"),
        ([8, 8, 7, 7, 6], 4, "Historical turning point zone"),
        ([9, 9, 8, 8, 7], 5, "Historical turning point zone"),
    ],
)
def test_active_force_count(scores: list[int], expected_count: int, expected_bucket: str) -> None:
    d = FiveForcesDashboard()
    out = d.T3_compute(
        metrics={
            "force_debt_money": scores[0],
            "force_political": scores[1],
            "force_geopolitical": scores[2],
            "force_technology": scores[3],
            "force_natural": scores[4],
        },
        portfolio=None,
    )
    assert out["active_force_count"] == expected_count
    assert out["bucket"] == expected_bucket


def test_t5_scoring_anchors_rescaled_in_drift() -> None:
    d = FiveForcesDashboard()
    base = {"anchor_high": 7.0, "anchor_critical": 9.0}
    out = d.T5_smart_mode_adjustments(
        base_thresholds=base,
        context={"smart_mode": True, "baseline_drift": 0.5},
    )
    assert out["anchor_high"] < 7.0
    assert out["anchor_critical"] <= 9.0
