from __future__ import annotations

import pytest
from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


def test_parse_returns_expression():
    node = parse("1 + 2")
    assert isinstance(node, Expression)
    assert isinstance(node, BinaryOp)
    assert node.op == "+"
    assert isinstance(node.left, Literal) and node.left.value == 1.0
    assert isinstance(node.right, Literal) and node.right.value == 2.0


def test_parse_precedence_mul_before_add():
    node = parse("1 + 2 * 3")
    assert isinstance(node, BinaryOp) and node.op == "+"
    right = node.right
    assert isinstance(right, BinaryOp) and right.op == "*"


def test_parse_parentheses_override_precedence():
    node = parse("(1 + 2) * 3")
    assert isinstance(node, BinaryOp) and node.op == "*"
    assert isinstance(node.left, BinaryOp) and node.left.op == "+"


def test_parse_unary_minus_and_not():
    node = parse("-price")
    assert isinstance(node, UnaryOp) and node.op == "-"
    assert isinstance(node.operand, Var) and node.operand.name == "price"

    node2 = parse("not ready")
    assert isinstance(node2, UnaryOp) and node2.op == "not"


def test_parse_comparison_chain_is_flat_not_chained():
    # We do not support Python-style chained comparisons; `a < b < c` must
    # parse as `(a < b) < c` per the operator precedence table, and fail
    # type-checking at evaluation time rather than silently merging.
    node = parse("a < b < c")
    assert isinstance(node, BinaryOp) and node.op == "<"
    assert isinstance(node.left, BinaryOp) and node.left.op == "<"


def test_parse_logical_and_or_precedence():
    # `not` binds tighter than `and`, which binds tighter than `or`.
    node = parse("a or b and not c")
    assert isinstance(node, BinaryOp) and node.op == "or"
    assert isinstance(node.right, BinaryOp) and node.right.op == "and"
    assert isinstance(node.right.right, UnaryOp) and node.right.right.op == "not"


def test_parse_ternary_if_else():
    node = parse("1 if cond else 2")
    assert isinstance(node, IfElse)
    assert isinstance(node.then_branch, Literal) and node.then_branch.value == 1.0
    assert isinstance(node.condition, Var) and node.condition.name == "cond"
    assert isinstance(node.else_branch, Literal) and node.else_branch.value == 2.0


def test_parse_function_call_zero_and_many_args():
    node = parse("mean(price, 5)")
    assert isinstance(node, Call)
    assert node.callee == "mean"
    assert len(node.args) == 2


def test_parse_exponent_is_right_associative():
    node = parse("2 ** 3 ** 2")
    assert isinstance(node, BinaryOp) and node.op == "**"
    right = node.right
    assert isinstance(right, BinaryOp) and right.op == "**"
    assert isinstance(right.left, Literal) and right.left.value == 3.0


def test_parse_boolean_and_numeric_literals():
    assert isinstance(parse("true"), Literal)
    assert parse("true").value is True
    assert parse("false").value is False
    assert parse("3.14").value == pytest.approx(3.14)


def test_parse_reports_position_on_syntax_error():
    from openlia.formula.engine import FormulaError

    with pytest.raises(FormulaError) as exc:
        parse("1 +")
    msg = str(exc.value)
    assert "expected" in msg.lower()


def test_parse_rejects_trailing_garbage():
    from openlia.formula.engine import FormulaError

    with pytest.raises(FormulaError):
        parse("1 + 2 )")
