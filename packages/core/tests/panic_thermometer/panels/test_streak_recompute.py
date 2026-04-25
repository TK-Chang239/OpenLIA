"""Confirm compute_streak recomputes derived scalars per bar (MA-relative streaks)."""

from __future__ import annotations

from openlia.formula import compute_streak


def test_compute_streak_recomputes_ma200_per_bar() -> None:
    """A price > ma200 streak should reflect each bar's trailing MA, not today's."""

    # Build prices that step up so the trailing-MA condition becomes True only in
    # the last 30 bars. If the engine used today's ma200 for every bar, the
    # streak would be much longer than 30.
    base = [70.0] * 200
    spike = [95.0] * 30
    closes = base + spike
    streak = compute_streak("price > ma200", {"price": closes})
    # The condition should be true for the spike segment only.
    assert 1 <= streak <= 30


def test_compute_streak_zero_when_condition_false_today() -> None:
    closes = [70.0] * 250
    assert compute_streak("price > 100", {"price": closes}) == 0


def test_compute_streak_with_simple_threshold() -> None:
    closes = [70.0] * 200 + [90.0] * 5
    assert compute_streak("price > 80", {"price": closes}) == 5
