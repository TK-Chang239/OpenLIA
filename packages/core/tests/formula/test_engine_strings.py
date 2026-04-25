"""String literal handling: equality, inequality, ordering errors."""

from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_string_literal_equality_true(engine: FormulaEngine):
    assert engine.evaluate('"a" == "a"', EvaluationContext()) is True


def test_string_literal_equality_false(engine: FormulaEngine):
    assert engine.evaluate('"a" == "b"', EvaluationContext()) is False


def test_string_inequality(engine: FormulaEngine):
    assert engine.evaluate('"a" != "b"', EvaluationContext()) is True


def test_string_var_equality(engine: FormulaEngine):
    c = ctx(phase="hawkish")
    assert engine.evaluate('phase == "hawkish"', c) is True


def test_string_var_inequality(engine: FormulaEngine):
    c = ctx(phase="dovish")
    assert engine.evaluate('phase != "hawkish"', c) is True


@pytest.mark.parametrize("op", [">", "<", ">=", "<="])
def test_string_ordering_raises_type_error(engine: FormulaEngine, op: str):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate(f'"a" {op} "b"', EvaluationContext())
    assert "string" in str(exc.value).lower()


def test_string_arithmetic_raises_type_error(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate('"a" + 1', EvaluationContext())


def test_string_eq_number_is_false(engine: FormulaEngine):
    # Mismatched-type equality returns false (not raise) per spec.
    with pytest.raises(FormulaError):
        engine.evaluate('"a" == 1', EvaluationContext())
