"""compute_streak: backtest a condition over the trailing close series."""

from __future__ import annotations

import pytest
from openlia.formula import compute_streak


def test_streak_fixed_threshold_3_bars():
    closes = [80.0, 82.0, 84.0, 86.0, 88.0, 90.0]  # last 3 above 85
    n = compute_streak(
        "price > threshold",
        {"price": closes},
        params={"threshold": 85.0},
    )
    assert n == 3


def test_streak_fixed_threshold_30_bars():
    closes = [50.0] * 100 + [120.0] * 30
    n = compute_streak(
        "price > 85",
        {"price": closes},
    )
    assert n == 30


def test_streak_fixed_threshold_90_bars():
    closes = [50.0] * 50 + [120.0] * 90
    n = compute_streak(
        "price > 85",
        {"price": closes},
    )
    assert n == 90


def test_streak_empty_returns_zero():
    n = compute_streak("price > 0", {"price": []})
    assert n == 0


def test_streak_all_false():
    closes = [10.0, 20.0, 30.0]
    n = compute_streak("price > 100", {"price": closes})
    assert n == 0


def test_streak_all_true():
    closes = [10.0, 20.0, 30.0, 40.0]
    n = compute_streak("price > 0", {"price": closes})
    assert n == 4


def test_streak_ma_relative_recomputes_per_bar():
    """MA200 changes bar by bar; the streak must use the bar-of-evaluation MA200."""
    # Build a series where the last 50 bars are all above the trailing MA200.
    base = [100.0] * 200
    rising = [110.0 + i * 0.1 for i in range(50)]
    closes = base + rising
    n = compute_streak(
        "price > ma200",
        {"price": closes},
    )
    # Ensure the streak picks up the trailing run; exact length depends on MA200 catch-up,
    # but it must be > 0 and <= 50.
    assert 1 <= n <= 50


def test_streak_breaks_on_first_false_from_end():
    closes = [10.0, 90.0, 90.0, 50.0, 90.0, 90.0]
    n = compute_streak("price > 80", {"price": closes})
    assert n == 2


def test_streak_no_price_series_returns_zero():
    n = compute_streak("true", {"other": [1.0, 2.0, 3.0]})
    assert n == 0


def test_streak_insufficient_history_for_ma200_truncates():
    # Only 50 bars - MA200 will be None for every bar; condition is false everywhere.
    closes = [120.0] * 50
    n = compute_streak("price > ma200", {"price": closes})
    assert n == 0


@pytest.mark.parametrize("length", [1, 5, 10, 50])
def test_streak_uniform_above(length: int):
    closes = [100.0] * length
    n = compute_streak("price > 50", {"price": closes})
    assert n == length
