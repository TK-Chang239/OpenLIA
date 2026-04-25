"""Event-driven functions: days_since, consecutive."""

from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_days_since_simple(engine: FormulaEngine):
    ctx = EvaluationContext(
        events=[{"event_type": "FOMC", "days_ago": 14}],
    )
    assert engine.evaluate('days_since("FOMC")', ctx) == 14


def test_days_since_picks_smallest_when_multiple(engine: FormulaEngine):
    ctx = EvaluationContext(
        events=[
            {"event_type": "FOMC", "days_ago": 60},
            {"event_type": "FOMC", "days_ago": 14},
            {"event_type": "FOMC", "days_ago": 100},
        ],
    )
    assert engine.evaluate('days_since("FOMC")', ctx) == 14


def test_days_since_no_match_returns_null(engine: FormulaEngine):
    ctx = EvaluationContext(events=[])
    assert engine.evaluate('days_since("FOMC")', ctx) is None


def test_days_since_event_lacks_days_ago_returns_null(engine: FormulaEngine):
    ctx = EvaluationContext(events=[{"event_type": "FOMC"}])
    assert engine.evaluate('days_since("FOMC")', ctx) is None


def test_days_since_filter_by_event_type(engine: FormulaEngine):
    ctx = EvaluationContext(
        events=[
            {"event_type": "CPI", "days_ago": 5},
            {"event_type": "FOMC", "days_ago": 30},
        ],
    )
    assert engine.evaluate('days_since("FOMC")', ctx) == 30


def test_consecutive_above_threshold(engine: FormulaEngine):
    ctx = EvaluationContext(history={"price": [80.0, 82.0, 90.0, 88.0, 91.0]})
    # last 3 above 85
    assert engine.evaluate('consecutive(price, ">", 85)', ctx) == 3


def test_consecutive_below_threshold(engine: FormulaEngine):
    ctx = EvaluationContext(history={"price": [10.0, 5.0, 4.0, 3.0]})
    assert engine.evaluate('consecutive(price, "<", 6)', ctx) == 3


def test_consecutive_zero_when_last_breaks(engine: FormulaEngine):
    ctx = EvaluationContext(history={"price": [90.0, 90.0, 50.0]})
    assert engine.evaluate('consecutive(price, ">", 85)', ctx) == 0


def test_consecutive_all_match(engine: FormulaEngine):
    ctx = EvaluationContext(history={"price": [90.0, 91.0, 92.0]})
    assert engine.evaluate('consecutive(price, ">", 85)', ctx) == 3


def test_consecutive_eq_op(engine: FormulaEngine):
    ctx = EvaluationContext(history={"price": [80.0, 90.0, 90.0, 90.0]})
    assert engine.evaluate('consecutive(price, "==", 90)', ctx) == 3
