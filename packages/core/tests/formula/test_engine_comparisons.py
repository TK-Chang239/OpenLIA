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
        ("1 < 2", True),
        ("2 < 1", False),
        ("3 <= 3", True),
        ("4 > 2", True),
        ("4 >= 5", False),
        ("1 == 1", True),
        ("1 != 2", True),
    ],
)
def test_numeric_comparisons(engine: FormulaEngine, src: str, expected: bool):
    assert engine.evaluate(src, EvaluationContext()) is expected


def test_string_equality_works(engine: FormulaEngine):
    # Strings may only compare with == / !=.
    assert engine.evaluate("status == status", ctx(status="red")) is True


def test_string_ordering_raises(engine: FormulaEngine):
    with pytest.raises(FormulaError) as exc:
        engine.evaluate("status < status", ctx(status="red"))
    assert "order" in str(exc.value).lower() or "numeric" in str(exc.value).lower()
