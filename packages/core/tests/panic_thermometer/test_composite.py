import pytest
from openlia.panic_thermometer.composite import compute_composite


def test_composite_count_zero_red_is_calm():
    r = compute_composite(
        {
            "oil": "green",
            "inflation": "green",
            "fed_language": "green",
            "wage_growth": "green",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "calm"
    assert r.red_count == 0


def test_composite_count_one_red_is_elevated():
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "green",
            "fed_language": "green",
            "wage_growth": "green",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "elevated"
    assert r.red_count == 1


def test_composite_count_at_threshold_is_high():
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "red",
            "fed_language": "green",
            "wage_growth": "green",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "high"
    assert r.red_count == 2


def test_composite_count_three_red_is_severe():
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "red",
            "fed_language": "red",
            "wage_growth": "green",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "severe"


def test_composite_count_four_red_is_crisis():
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "dark_red",
            "fed_language": "red",
            "wage_growth": "red",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "crisis"
    assert r.red_count == 4


def test_composite_weighted_sums_weights():
    settings = {
        "mode": "weighted",
        "weights": {
            "oil": 1.0,
            "inflation": 1.0,
            "fed_language": 0.8,
            "wage_growth": 1.0,
            "diplomacy": 0.5,
        },
        "thresholds": {"elevated": 1.0, "high": 2.0, "severe": 3.0, "crisis": 4.0},
    }
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "red",
            "fed_language": "red",
            "wage_growth": "green",
            "diplomacy": "green",
        },
        settings,
    )
    assert pytest.approx(r.score) == 2.8
    assert r.level == "high"


def test_composite_disabled_panels_ignored():
    r = compute_composite(
        {
            "oil": "red",
            "inflation": "disabled",
            "fed_language": "red",
            "wage_growth": "disabled",
            "diplomacy": "green",
        },
        {"mode": "count", "red_threshold": 2},
    )
    assert r.red_count == 2
    assert r.level == "high"
