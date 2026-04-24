from __future__ import annotations

import pytest
from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.formula.engine import MAX_AST_DEPTH, MAX_EVAL_STEPS, MAX_NODE_COUNT
from openlia.formula.parser import parse


def test_max_ast_depth_is_enforced_at_parse_time():
    # Build a deeply-nested expression that exceeds the depth cap.
    depth = MAX_AST_DEPTH + 2
    source = "(" * depth + "1" + ")" * depth
    with pytest.raises(FormulaError) as exc:
        parse(source)
    assert "depth" in str(exc.value).lower()


def test_max_node_count_is_enforced_at_parse_time():
    # A long chain of + operations easily exceeds the node cap.
    terms = ["1"] * (MAX_NODE_COUNT + 5)
    source = " + ".join(terms)
    with pytest.raises(FormulaError) as exc:
        parse(source)
    assert "node" in str(exc.value).lower() or "complex" in str(exc.value).lower()


def test_max_eval_steps_is_enforced_at_runtime():
    # Construct a prebuilt balanced-tree AST that bypasses parser caps but
    # triggers the evaluator's step counter. Each BinaryOp adds ~1 step;
    # a tree with > MAX_EVAL_STEPS nodes trips the guard while keeping
    # depth small (log2 of size).
    from openlia.formula.parser import BinaryOp, Literal

    engine = FormulaEngine()

    def build(n: int):
        if n == 0:
            return Literal(value=1.0)
        return BinaryOp("+", build(n - 1), build(n - 1))

    # 2^14 leaves = 16384 nodes, depth 14. Exceeds MAX_EVAL_STEPS (10_000).
    tree = build(14)
    with pytest.raises(FormulaError) as exc:
        engine.evaluate(tree, EvaluationContext())
    assert "step" in str(exc.value).lower()


def test_safety_limits_are_public_constants():
    assert isinstance(MAX_AST_DEPTH, int) and MAX_AST_DEPTH > 0
    assert isinstance(MAX_NODE_COUNT, int) and MAX_NODE_COUNT > 0
    assert isinstance(MAX_EVAL_STEPS, int) and MAX_EVAL_STEPS > 0
