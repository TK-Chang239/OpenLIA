"""Null literal + null propagation rules."""

from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_null_literal_evaluates_to_none(engine: FormulaEngine):
    assert engine.evaluate("null", EvaluationContext()) is None


# --- Equality rules from spec ---


def test_null_eq_null_is_true(engine: FormulaEngine):
    assert engine.evaluate("null == null", EvaluationContext()) is True


def test_null_neq_null_is_false(engine: FormulaEngine):
    assert engine.evaluate("null != null", EvaluationContext()) is False


def test_null_eq_value_is_false(engine: FormulaEngine):
    assert engine.evaluate("null == 1", EvaluationContext()) is False
    assert engine.evaluate("1 == null", EvaluationContext()) is False


def test_null_neq_value_is_true(engine: FormulaEngine):
    assert engine.evaluate("null != 1", EvaluationContext()) is True
    assert engine.evaluate("1 != null", EvaluationContext()) is True


def test_null_lt_value_is_false(engine: FormulaEngine):
    assert engine.evaluate("null < 1", EvaluationContext()) is False
    assert engine.evaluate("1 < null", EvaluationContext()) is False


def test_null_gte_value_is_false(engine: FormulaEngine):
    assert engine.evaluate("null >= 1", EvaluationContext()) is False
    assert engine.evaluate("1 >= null", EvaluationContext()) is False


# --- Arithmetic propagation ---


@pytest.mark.parametrize(
    "src",
    [
        "null + 1",
        "1 + null",
        "null - 5",
        "null * 2",
        "null / 2",
        "10 / null",
        "null % 3",
        "null ** 2",
    ],
)
def test_arithmetic_with_null_returns_null(engine: FormulaEngine, src: str):
    assert engine.evaluate(src, EvaluationContext()) is None


def test_unary_minus_null_is_null(engine: FormulaEngine):
    assert engine.evaluate("-null", EvaluationContext()) is None


# --- Logical short-circuit guards ---


def test_and_short_circuits_on_false_even_with_null_right(engine: FormulaEngine):
    # left is False -> short-circuit, never evaluates the null on the right.
    assert engine.evaluate("false and null", EvaluationContext()) is False


def test_or_short_circuits_on_true_even_with_null_right(engine: FormulaEngine):
    assert engine.evaluate("true or null", EvaluationContext()) is True


def test_and_with_null_left_and_true_right_is_null(engine: FormulaEngine):
    assert engine.evaluate("null and true", EvaluationContext()) is None


def test_or_with_null_left_and_false_right_is_null(engine: FormulaEngine):
    assert engine.evaluate("null or false", EvaluationContext()) is None


def test_not_null_is_null(engine: FormulaEngine):
    assert engine.evaluate("not null", EvaluationContext()) is None


# --- If/else with null condition ---


def test_if_null_condition_returns_null(engine: FormulaEngine):
    assert engine.evaluate("1 if null else 2", EvaluationContext()) is None


def test_null_propagation_through_variable(engine: FormulaEngine):
    c = ctx(x=None)
    assert engine.evaluate("x + 1", c) is None


def test_null_in_string_equality(engine: FormulaEngine):
    c = ctx(name=None)
    assert engine.evaluate('name == "x"', c) is False
    assert engine.evaluate("name == null", c) is True
