from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_and_or_not_evaluation(engine: FormulaEngine):
    assert engine.evaluate("true and false", EvaluationContext()) is False
    assert engine.evaluate("true or false", EvaluationContext()) is True
    assert engine.evaluate("not true", EvaluationContext()) is False


def test_short_circuit_and_skips_rhs(engine: FormulaEngine):
    # `ghost` is undefined; if we short-circuit we must not look it up.
    result = engine.evaluate("false and ghost", EvaluationContext())
    assert result is False


def test_short_circuit_or_skips_rhs(engine: FormulaEngine):
    result = engine.evaluate("true or ghost", EvaluationContext())
    assert result is True


def test_ternary_selects_then_branch(engine: FormulaEngine):
    assert engine.evaluate("1 if true else 2", EvaluationContext()) == 1.0


def test_ternary_selects_else_branch(engine: FormulaEngine):
    assert engine.evaluate("1 if false else 2", EvaluationContext()) == 2.0


def test_ternary_short_circuits_unused_branch(engine: FormulaEngine):
    # Division by zero in the unused branch must not explode.
    assert engine.evaluate("1 if true else 1/0", EvaluationContext()) == 1.0


def test_logical_requires_boolean_operands(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("1 and 2", EvaluationContext())
