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
        series = ctx.history.get(node.name)
        if series is None:
            raise FormulaError(
                f"undefined historical series {node.name!r}",
                line=node.line,
                col=node.col,
            )
        if node.lag >= len(series):
            raise FormulaError(
                f"history for {node.name!r} needs >= {node.lag + 1} entries, got {len(series)}",
                line=node.line,
                col=node.col,
            )
        return float(series[-1 - node.lag])

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


import statistics as _stats  # noqa: E402


def _eval_args_as_numbers(node: Call, ctx: EvaluationContext, state: _EvalState) -> list[float]:
    out: list[float] = []
    for arg in node.args:
        val = _eval_node(arg, ctx, state)
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise FormulaError(
                f"function {node.callee!r} requires numeric args, got {type(val).__name__}",
                line=node.line,
                col=node.col,
            )
        out.append(float(val))
    return out


def _impl_min(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    return min(_eval_args_as_numbers(node, ctx, state))


def _impl_max(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    return max(_eval_args_as_numbers(node, ctx, state))


def _impl_abs(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return abs(args[0])


def _impl_round(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    if len(args) == 1:
        return float(round(args[0]))
    # Python's round accepts a negative ndigits; clamp to int.
    return float(round(args[0], int(args[1])))


def _impl_mean(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return sum(args) / len(args)


def _impl_median(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return float(_stats.median(args))


def _impl_stddev(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    if len(args) < 2:
        raise FormulaError(
            "stddev requires at least two values",
            line=node.line,
            col=node.col,
        )
    return float(_stats.stdev(args))


def _impl_sum(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    args = _eval_args_as_numbers(node, ctx, state)
    return float(sum(args))


FUNCTION_REGISTRY.update(
    {
        "min": _FunctionSpec("min", 1, 64, False, _impl_min),
        "max": _FunctionSpec("max", 1, 64, False, _impl_max),
        "abs": _FunctionSpec("abs", 1, 1, False, _impl_abs),
        "round": _FunctionSpec("round", 1, 2, False, _impl_round),
        "mean": _FunctionSpec("mean", 1, 64, False, _impl_mean),
        "median": _FunctionSpec("median", 1, 64, False, _impl_median),
        "stddev": _FunctionSpec("stddev", 1, 64, False, _impl_stddev),
        "sum": _FunctionSpec("sum", 1, 64, False, _impl_sum),
    }
)


def _history_arg(node: Call, ctx: EvaluationContext, index: int = 0) -> tuple[str, list[float]]:
    if not node.args or not isinstance(node.args[index], Var):
        raise FormulaError(
            f"function {node.callee!r} requires a bare variable as argument {index + 1}",
            line=node.line,
            col=node.col,
        )
    name = node.args[index].name  # type: ignore[attr-defined]
    series = ctx.history.get(name)
    if series is None:
        raise FormulaError(
            f"undefined historical series {name!r}",
            line=node.line,
            col=node.col,
        )
    return name, list(series)


def _int_arg(node: Call, ctx: EvaluationContext, state: _EvalState, index: int) -> int:
    val = _eval_node(node.args[index], ctx, state)
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise FormulaError(
            f"function {node.callee!r} requires an integer argument",
            line=node.line,
            col=node.col,
        )
    if float(val).is_integer() is False or val < 0:
        raise FormulaError(
            f"function {node.callee!r} requires a non-negative integer",
            line=node.line,
            col=node.col,
        )
    return int(val)


def _impl_last(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    if len(node.args) == 1:
        _, series = _history_arg(node, ctx)
        if not series:
            raise FormulaError(
                f"last({node.args[0]}) requires non-empty history",
                line=node.line,
                col=node.col,
            )
        return float(series[-1])
    # last(series, n) returns the value n positions back (shorthand).
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        raise FormulaError(
            f"last({name}, {n}) requires history of at least {n} entries",
            line=node.line,
            col=node.col,
        )
    return float(series[-n])


def _impl_pct_change(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n <= 0 or n >= len(series):
        raise FormulaError(
            f"pct_change({name}, {n}) requires history of at least {n + 1} entries",
            line=node.line,
            col=node.col,
        )
    previous = series[-1 - n]
    current = series[-1]
    if previous == 0:
        raise FormulaError(
            f"pct_change({name}, {n}): prior value is zero",
            line=node.line,
            col=node.col,
        )
    return (current - previous) / previous * 100.0


def _impl_rolling_mean(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        raise FormulaError(
            f"rolling_mean({name}, {n}): history has only {len(series)} entries",
            line=node.line,
            col=node.col,
        )
    window = series[-n:]
    return sum(window) / float(n)


def _impl_lag(node: Call, ctx: EvaluationContext, state: _EvalState) -> float:
    name, series = _history_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n >= len(series):
        raise FormulaError(
            f"lag({name}, {n}): history has only {len(series)} entries",
            line=node.line,
            col=node.col,
        )
    return float(series[-1 - n])


FUNCTION_REGISTRY.update(
    {
        "last": _FunctionSpec("last", 1, 2, True, _impl_last),
        "pct_change": _FunctionSpec("pct_change", 2, 2, True, _impl_pct_change),
        "rolling_mean": _FunctionSpec("rolling_mean", 2, 2, True, _impl_rolling_mean),
        "lag": _FunctionSpec("lag", 2, 2, True, _impl_lag),
    }
)
