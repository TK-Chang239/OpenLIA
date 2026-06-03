"""Deterministic world_order classifier tests.

Parallels test_classification.py for debt_cycle: pure thresholds, no I/O.
"""

from openlia.macro_research.quant.world_order import (
    WorldOrderInputs,
    classify_world_order,
)


def test_all_green_inputs_early_stage():
    out = classify_world_order(
        WorldOrderInputs(
            usd_reserve_share=70.0,
            cb_gold_purchases=200.0,
            foreign_treasury_trend=5.0,
            dxy=110.0,
        )
    )
    assert out.stage == "Early (Stage 3)"
    assert out.severity == "green"
    assert out.red_count == 0
    assert out.amber_count == 0
    assert set(out.indicator_statuses.values()) == {"green"}


def test_two_red_inputs_late_stage():
    out = classify_world_order(
        WorldOrderInputs(
            usd_reserve_share=50.0,  # red (<= 55)
            cb_gold_purchases=900.0,  # red (>= 800)
            foreign_treasury_trend=5.0,  # green
            dxy=110.0,  # green
        )
    )
    assert out.stage == "Late (Stage 5-6)"
    assert out.severity == "red"
    assert out.red_count == 2


def test_one_red_mid_stage():
    out = classify_world_order(
        WorldOrderInputs(
            usd_reserve_share=50.0,  # red
            cb_gold_purchases=200.0,  # green
            foreign_treasury_trend=5.0,  # green
            dxy=110.0,  # green
        )
    )
    assert out.stage == "Mid (Stage 4-5)"
    assert out.severity == "amber"
    assert out.red_count == 1
    assert out.amber_count == 0


def test_two_amber_mid_stage():
    out = classify_world_order(
        WorldOrderInputs(
            usd_reserve_share=58.0,  # amber (<= 60, > 55)
            cb_gold_purchases=500.0,  # amber (>= 400, < 800)
            foreign_treasury_trend=5.0,  # green
            dxy=110.0,  # green
        )
    )
    assert out.stage == "Mid (Stage 4-5)"
    assert out.severity == "amber"
    assert out.red_count == 0
    assert out.amber_count == 2


def test_indicator_status_keys_present():
    out = classify_world_order(
        WorldOrderInputs(
            usd_reserve_share=56.9,
            cb_gold_purchases=863.0,
            foreign_treasury_trend=8.0,
            dxy=98.7,
        )
    )
    assert set(out.indicator_statuses) == {
        "usd_reserve_share",
        "cb_gold_purchases",
        "foreign_treasury_trend",
        "dxy",
    }
