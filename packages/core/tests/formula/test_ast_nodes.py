from __future__ import annotations

from openlia.formula.parser import (
    BinaryOp,
    Call,
    Expression,
    HistoricalVar,
    IfElse,
    Literal,
    UnaryOp,
    Var,
    parse,
)


def test_every_node_class_inherits_expression():
    classes = [BinaryOp, Call, HistoricalVar, IfElse, Literal, UnaryOp, Var]
    for cls in classes:
        assert issubclass(cls, Expression), cls.__name__


def test_literal_attribute_shape():
    node = parse("3.14")
    assert isinstance(node, Literal)
    assert node.value == 3.14
    assert hasattr(node, "line") and hasattr(node, "col")


def test_var_carries_name_and_position():
    node = parse("ma200")
    assert isinstance(node, Var)
    assert node.name == "ma200"
    assert node.col == 1


def test_binary_op_has_op_left_right():
    node = parse("a + b")
    assert isinstance(node, BinaryOp)
    for attr in ("op", "left", "right", "line", "col"):
        assert hasattr(node, attr)


def test_unary_op_has_op_and_operand():
    node = parse("-x")
    assert isinstance(node, UnaryOp)
    assert node.op == "-"
    assert hasattr(node, "operand")


def test_call_has_callee_and_args():
    node = parse("max(a, b, 3)")
    assert isinstance(node, Call)
    assert node.callee == "max"
    assert len(node.args) == 3


def test_if_else_has_condition_then_else():
    node = parse("1 if cond else 2")
    assert isinstance(node, IfElse)
    assert hasattr(node, "condition")
    assert hasattr(node, "then_branch")
    assert hasattr(node, "else_branch")


def test_nodes_are_dataclass_equal():
    assert parse("1 + 2") == parse("1 + 2")
    assert parse("1 + 2") != parse("2 + 1")


def test_nodes_repr_is_useful():
    text = repr(parse("1 + 2"))
    assert "BinaryOp" in text
    assert "Literal" in text
