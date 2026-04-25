"""Strict type discipline matrix."""

from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError, TypeMismatchError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


# --- Numeric returns float ---


def test_int_literal_returns_float(engine: FormulaEngine):
    assert engine.evaluate("3", EvaluationContext()) == 3.0


def test_addition_returns_float(engine: FormulaEngine):
    result = engine.evaluate("1 + 2", EvaluationContext())
    assert result == 3.0
    assert isinstance(result, float)


def test_negative_returns_float(engine: FormulaEngine):
    assert engine.evaluate("-5", EvaluationContext()) == -5.0


# --- Type errors ---


def test_string_plus_number_raises_type_error(engine: FormulaEngine):
    with pytest.raises(TypeMismatchError):
        engine.evaluate('"x" + 1', EvaluationContext())


def test_bool_plus_number_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("true + 1", EvaluationContext())


def test_logical_not_on_number_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("not 1", EvaluationContext())


def test_and_on_number_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("1 and 2", EvaluationContext())


def test_compare_string_with_number_eq_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate('"x" == 1', EvaluationContext())


def test_compare_bool_with_number_eq_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("true == 1", EvaluationContext())


def test_string_lt_string_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate('"a" < "b"', EvaluationContext())


def test_compare_bool_with_bool_eq_ok(engine: FormulaEngine):
    assert engine.evaluate("true == true", EvaluationContext()) is True
    assert engine.evaluate("true == false", EvaluationContext()) is False


# --- Identifier coercion ---


def test_int_var_coerced_to_float(engine: FormulaEngine):
    c = ctx(x=3)
    assert engine.evaluate("x + 0", c) == 3.0


def test_bool_var_preserved(engine: FormulaEngine):
    c = ctx(b=True)
    assert engine.evaluate("b", c) is True


def test_string_var_preserved(engine: FormulaEngine):
    c = ctx(s="hello")
    assert engine.evaluate("s", c) == "hello"
