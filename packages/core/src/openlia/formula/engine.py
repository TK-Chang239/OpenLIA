"""Safe, deterministic evaluator for the formula DSL.

This module owns three public names:

    FormulaEngine       -- entry point; stateless across calls
    EvaluationContext   -- dict wrappers for values + history
    FormulaError        -- every error surfaces as this or a subclass
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class FormulaError(Exception):
    """Parse/evaluation failure with optional source position."""

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        col: int | None = None,
    ) -> None:
        if line is not None and col is not None:
            super().__init__(f"{message} (line {line}, col {col})")
        else:
            super().__init__(message)
        self.line = line
        self.col = col


@dataclass
class EvaluationContext:
    values: dict[str, float | bool | str] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)


# Safety caps -- public constants so tests can import them.
MAX_AST_DEPTH = 64
MAX_NODE_COUNT = 1024
MAX_EVAL_STEPS = 10_000


# Function registry landed here; full population in Tasks 5 & 6.
@dataclass(frozen=True, slots=True)
class _FunctionSpec:
    name: str
    min_args: int
    max_args: int
    needs_history: bool
    impl: Any  # Callable — annotated loosely to avoid heavy typing imports.


FUNCTION_REGISTRY: dict[str, _FunctionSpec] = {}


# Imports are placed after FormulaError / EvaluationContext so parser can
# import FormulaError without a cycle.
from openlia.formula.parser import (  # noqa: E402
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


class FormulaEngine:
    """Evaluate an expression (source string or pre-parsed AST) against a context."""

    def evaluate(self, expr: str | Expression, context: EvaluationContext) -> float | bool:
        if isinstance(expr, str):
            tree = parse(expr)
        else:
            tree = expr
        state = _EvalState()
        result = _eval_node(tree, context, state)
        return _coerce_final(result)


@dataclass
class _EvalState:
    steps: int = 0


def _step(state: _EvalState) -> None:
    state.steps += 1
    if state.steps > MAX_EVAL_STEPS:
        raise FormulaError(f"evaluation exceeded {MAX_EVAL_STEPS} steps; aborting")


def _coerce_final(value: Any) -> float | bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    raise FormulaError(f"formula produced non-numeric/non-boolean result: {type(value).__name__}")


def _require_number(value: Any, *, op: str, node: Expression) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FormulaError(
            f"operator {op!r} requires numeric operands, got {type(value).__name__}",
            line=node.line,
            col=node.col,
        )
    return float(value)


def _require_bool(value: Any, *, op: str, node: Expression) -> bool:
    if not isinstance(value, bool):
        raise FormulaError(
            f"operator {op!r} requires boolean operands, got {type(value).__name__}",
            line=node.line,
            col=node.col,
        )
    return value


def _eval_node(node: Expression, ctx: EvaluationContext, state: _EvalState) -> Any:
    _step(state)

    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Var):
        if node.name not in ctx.values:
            raise FormulaError(
                f"undefined variable {node.name!r}",
                line=node.line,
                col=node.col,
            )
        return ctx.values[node.name]

    if isinstance(node, HistoricalVar):
        # Body lands in Task 6; for now raise to keep behaviour explicit.
        raise FormulaError(
            "historical variables land in Task 6",
            line=node.line,
            col=node.col,
        )

    if isinstance(node, UnaryOp):
        operand = _eval_node(node.operand, ctx, state)
        if node.op == "-":
            return -_require_number(operand, op="-", node=node)
        if node.op == "not":
            return not _require_bool(operand, op="not", node=node)
        raise FormulaError(
            f"unknown unary operator {node.op!r}",
            line=node.line,
            col=node.col,
        )

    if isinstance(node, BinaryOp):
        return _eval_binary(node, ctx, state)

    if isinstance(node, IfElse):
        cond = _eval_node(node.condition, ctx, state)
        cond_b = _require_bool(cond, op="if", node=node)
        branch = node.then_branch if cond_b else node.else_branch
        return _eval_node(branch, ctx, state)

    if isinstance(node, Call):
        return _eval_call(node, ctx, state)

    raise FormulaError(
        f"unsupported AST node {type(node).__name__}",
        line=node.line,
        col=node.col,
    )


def _eval_binary(node: BinaryOp, ctx: EvaluationContext, state: _EvalState) -> Any:
    op = node.op

    # Short-circuit logical operators.
    if op == "and":
        left = _require_bool(
            _eval_node(node.left, ctx, state),
            op="and",
            node=node,
        )
        if not left:
            return False
        return _require_bool(
            _eval_node(node.right, ctx, state),
            op="and",
            node=node,
        )
    if op == "or":
        left = _require_bool(
            _eval_node(node.left, ctx, state),
            op="or",
            node=node,
        )
        if left:
            return True
        return _require_bool(
            _eval_node(node.right, ctx, state),
            op="or",
            node=node,
        )

    left = _eval_node(node.left, ctx, state)
    right = _eval_node(node.right, ctx, state)

    if op in {"==", "!="}:
        # Strict equality — types must match.
        if type(left) is not type(right):
            # Allow int/float interop (both ultimately floats after coercion).
            if not (
                isinstance(left, (int, float))
                and isinstance(right, (int, float))
                and not isinstance(left, bool)
                and not isinstance(right, bool)
            ):
                raise FormulaError(
                    f"comparison {op!r} requires matching types, got "
                    f"{type(left).__name__} and {type(right).__name__}",
                    line=node.line,
                    col=node.col,
                )
        return (left == right) if op == "==" else (left != right)

    if op in {"<", "<=", ">", ">="}:
        ln = _require_number(left, op=op, node=node)
        rn = _require_number(right, op=op, node=node)
        return {
            "<": ln < rn,
            "<=": ln <= rn,
            ">": ln > rn,
            ">=": ln >= rn,
        }[op]

    # Arithmetic.
    ln = _require_number(left, op=op, node=node)
    rn = _require_number(right, op=op, node=node)
    if op == "+":
        return ln + rn
    if op == "-":
        return ln - rn
    if op == "*":
        return ln * rn
    if op == "/":
        if rn == 0.0:
            raise FormulaError(
                "division by zero",
                line=node.line,
                col=node.col,
            )
        return ln / rn
    if op == "%":
        if rn == 0.0:
            raise FormulaError(
                "modulo by zero",
                line=node.line,
                col=node.col,
            )
        return ln % rn
    if op == "**":
        return ln**rn

    raise FormulaError(
        f"unknown binary operator {op!r}",
        line=node.line,
        col=node.col,
    )


def _eval_call(node: Call, ctx: EvaluationContext, state: _EvalState) -> Any:
    spec = FUNCTION_REGISTRY.get(node.callee)
    if spec is None:
        raise FormulaError(
            f"unknown function {node.callee!r}",
            line=node.line,
            col=node.col,
        )
    if not (spec.min_args <= len(node.args) <= spec.max_args):
        raise FormulaError(
            f"function {node.callee!r} expects {spec.min_args}..{spec.max_args} "
            f"args, got {len(node.args)}",
            line=node.line,
            col=node.col,
        )
    return spec.impl(node, ctx, state)
