from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError, parse

from ._formula_fakes import ctx


@pytest.fixture
def engine() -> FormulaEngine:
    return FormulaEngine()


def test_parse_error_has_line_and_col():
    with pytest.raises(FormulaError) as exc:
        parse("1 + ")
    assert exc.value.line is not None
    assert exc.value.col is not None
    assert f"line {exc.value.line}" in str(exc.value)
    assert f"col {exc.value.col}" in str(exc.value)


def test_lex_error_surfaces_as_formula_error():
    with pytest.raises(FormulaError) as exc:
        parse("1 @ 2")
    assert exc.value.col == 3


def test_undefined_variable_error_carries_position(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("5 + missing_var", EvaluationContext())
    assert "missing_var" in str(exc.value)
    # Var position was populated in the parser.
    assert exc.value.line == 1


def test_type_error_carries_op_and_position(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("1 + name", ctx(name="x"))
    msg = str(exc.value)
    assert "numeric" in msg
    assert "+" in msg


def test_division_by_zero_returns_null_with_warning(engine: FormulaEngine):
    result = engine.evaluate_safe("5 / 0", EvaluationContext())
    assert result.value is None
    assert any("division" in w.lower() for w in result.warnings)


def test_insufficient_history_returns_null_with_warning(engine: FormulaEngine):
    result = engine.evaluate_safe(
        "price[t-10]",
        EvaluationContext(history={"price": [1.0, 2.0]}),
    )
    assert result.value is None
    joined = " ".join(result.warnings)
    assert "price" in joined
    assert "11" in joined  # needs >= 11 entries
