from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


@pytest.mark.parametrize(
    "src,expected",
    [
        ("1 + 2", 3.0),
        ("10 - 4", 6.0),
        ("3 * 4", 12.0),
        ("10 / 4", 2.5),
        ("10 % 3", 1.0),
        ("2 ** 3", 8.0),
        ("2 ** 3 ** 2", 512.0),
        ("-5 + 3", -2.0),
        ("(1 + 2) * 3", 9.0),
        ("1 + 2 * 3", 7.0),
    ],
)
def test_numeric_expressions(engine: FormulaEngine, src: str, expected: float):
    assert engine.evaluate(src, EvaluationContext()) == expected


def test_variable_lookup(engine: FormulaEngine):
    assert engine.evaluate("price * 2", ctx(price=10.0)) == 20.0


def test_division_by_zero_returns_null_with_warning(engine: FormulaEngine):
    result = engine.evaluate_safe("1 / 0", EvaluationContext())
    assert result.value is None
    assert any("division" in w.lower() for w in result.warnings)


def test_modulo_by_zero_returns_null_with_warning(engine: FormulaEngine):
    result = engine.evaluate_safe("5 % 0", EvaluationContext())
    assert result.value is None
    assert any("modulo" in w.lower() for w in result.warnings)


def test_undefined_variable_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("ghost + 1", EvaluationContext())
    assert "ghost" in str(exc.value)


def test_string_operand_is_type_error(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("name + 1", ctx(name="alice"))
    assert "numeric" in str(exc.value).lower()


def test_accepts_prebuilt_ast(engine: FormulaEngine):
    from openlia.formula import parse

    tree = parse("price + 1")
    assert engine.evaluate(tree, ctx(price=4.0)) == 5.0
