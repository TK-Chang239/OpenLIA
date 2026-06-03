"""Deterministic five_forces classifier tests.

Ports the legacy ``FiveForcesDashboard.T3_compute``: five 0-10 force-intensity
scores map to an active-force count (score >= 7), a bucket, and an overall RAG
severity. Pure function; no I/O, no LLM.
"""

from openlia.macro_research.quant.forces import ForceScores, classify_five_forces


def test_all_low_is_normal_green_zero_active() -> None:
    out = classify_five_forces(
        ForceScores(debt_money=3, political=4, geopolitical=4, technology=3, natural=2)
    )
    assert out.active_force_count == 0
    assert out.bucket == "Normal"
    assert out.severity == "green"


def test_one_active_is_normal_green() -> None:
    out = classify_five_forces(
        ForceScores(debt_money=7, political=5, geopolitical=3, technology=4, natural=6)
    )
    assert out.active_force_count == 1
    assert out.bucket == "Normal"
    assert out.severity == "green"


def test_three_active_is_elevated_amber() -> None:
    out = classify_five_forces(
        ForceScores(debt_money=8, political=7, geopolitical=7, technology=5, natural=4)
    )
    assert out.active_force_count == 3
    assert out.bucket == "Elevated"
    assert out.severity == "amber"


def test_four_active_is_turning_point_red() -> None:
    out = classify_five_forces(
        ForceScores(debt_money=8, political=8, geopolitical=7, technology=7, natural=6)
    )
    assert out.active_force_count == 4
    assert out.bucket == "Historical turning point zone"
    assert out.severity == "red"


def test_force_scores_round_trip_into_dict() -> None:
    out = classify_five_forces(
        ForceScores(debt_money=8.0, political=5.0, geopolitical=5.0, technology=4.0, natural=2.0)
    )
    assert out.force_scores == {
        "debt_money": 8.0,
        "political": 5.0,
        "geopolitical": 5.0,
        "technology": 4.0,
        "natural": 2.0,
    }
