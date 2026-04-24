from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


@pytest.mark.parametrize(
    "src,expected",
    [
        ("min(1, 2, 3)", 1.0),
        ("max(1, 2, 3)", 3.0),
        ("abs(-5)", 5.0),
        ("abs(5)", 5.0),
        ("round(2.6)", 3.0),
        ("round(2.45, 1)", 2.5),
        ("mean(1, 2, 3, 4)", 2.5),
        ("median(1, 2, 3)", 2.0),
        ("median(1, 2, 3, 4)", 2.5),
        ("sum(1, 2, 3)", 6.0),
    ],
)
def test_math_functions(engine: FormulaEngine, src: str, expected: float):
    assert engine.evaluate(src, EvaluationContext()) == pytest.approx(expected)


def test_stddev_matches_sample_formula(engine: FormulaEngine):
    # Sample stddev of [2,4,4,4,5,5,7,9] == 2.138089935...
    value = engine.evaluate("stddev(2, 4, 4, 4, 5, 5, 7, 9)", EvaluationContext())
    assert value == pytest.approx(2.138089935, rel=1e-6)


def test_stddev_requires_at_least_two_values(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("stddev(1)", EvaluationContext())
    assert "at least two" in str(exc.value).lower() or "two" in str(exc.value).lower()


def test_unknown_function_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("fibonacci(5)", EvaluationContext())
    assert "fibonacci" in str(exc.value)


def test_wrong_arity_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("abs(1, 2)", EvaluationContext())
    assert "args" in str(exc.value)


def test_nonnumeric_argument_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError):
        engine.evaluate("min(a, 1)", EvaluationContext(values={"a": "hi"}))
