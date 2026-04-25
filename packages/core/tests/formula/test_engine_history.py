from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx_with_history


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_historical_var_current_tick_is_zero_lag(engine: FormulaEngine):
    # `price[t-0]` is the last entry.
    history = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0]})
    assert engine.evaluate("price[t-0]", history) == 4.0


def test_historical_var_nonzero_lag(engine: FormulaEngine):
    history = ctx_with_history(history={"price": [10.0, 11.0, 12.0, 13.0]})
    assert engine.evaluate("price[t-1]", history) == 12.0
    assert engine.evaluate("price[t-3]", history) == 10.0


def test_historical_var_negative_lag_raises(engine: FormulaEngine):
    history = ctx_with_history(history={"price": [1.0]})
    with pytest.raises(FormulaError):
        engine.evaluate("price[t+1]", history)  # parser should not accept +
    # Insufficient-history now returns null + warning rather than raising.
    assert engine.evaluate("price[t-10]", history) is None
    assert engine.last_warnings


def test_historical_var_missing_series_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("ghost[t-0]", EvaluationContext())
    assert "ghost" in str(exc.value)


def test_last_returns_final_value(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0]})
    assert engine.evaluate("last(price)", h) == 3.0


def test_pct_change_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [100.0, 110.0, 121.0]})
    # pct_change(series, 1) -> (121-110)/110 * 100 = 10.0
    assert engine.evaluate("pct_change(price, 1)", h) == pytest.approx(10.0)
    # pct_change(series, 2) -> (121-100)/100 * 100 = 21.0
    assert engine.evaluate("pct_change(price, 2)", h) == pytest.approx(21.0)


def test_rolling_mean_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0, 5.0]})
    assert engine.evaluate("rolling_mean(price, 3)", h) == pytest.approx(4.0)


def test_rolling_mean_requires_enough_history(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0]})
    # Insufficient history returns null + warning per spec.
    assert engine.evaluate("rolling_mean(price, 5)", h) is None
    assert engine.last_warnings


def test_lag_n(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [1.0, 2.0, 3.0, 4.0]})
    # lag(price, 0) -> 4.0, lag(price, 1) -> 3.0, lag(price, 3) -> 1.0.
    assert engine.evaluate("lag(price, 0)", h) == 4.0
    assert engine.evaluate("lag(price, 1)", h) == 3.0
    assert engine.evaluate("lag(price, 3)", h) == 1.0


def test_pct_change_requires_positive_prior(engine: FormulaEngine):
    h = ctx_with_history(history={"price": [0.0, 10.0]})
    # Prior-zero now returns null + warning rather than raising.
    assert engine.evaluate("pct_change(price, 1)", h) is None
    assert engine.last_warnings


def test_history_func_first_arg_must_be_variable(engine: FormulaEngine):
    # The parser enforces this so requirement extraction is straightforward.
    h = ctx_with_history(history={"price": [1.0, 2.0]})
    with pytest.raises(FormulaError):
        engine.evaluate("rolling_mean(1 + 2, 3)", h)
