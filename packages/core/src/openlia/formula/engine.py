"""Safe, deterministic evaluator for the formula DSL."""

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
        position: int | None = None,
        identifier: str | None = None,
        type_: str | None = None,
    ) -> None:
        if line is not None and col is not None:
            super().__init__(f"{message} (line {line}, col {col})")
        else:
            super().__init__(message)
        self.line = line
        self.col = col
        self.position = position if position is not None else col
        self.identifier = identifier
        self.type_ = type_


class ParseError(FormulaError):
    """Syntax / lexer / parser error."""


class UnknownIdentifierError(FormulaError):
    """Reference to an identifier not present in the evaluation context."""


class TypeMismatchError(FormulaError):
    """Operand or argument has the wrong type for the operation."""


@dataclass
class EvaluationContext:
    values: dict[str, float | bool | str | None] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_raw_series(
        cls,
        raw_series: dict[str, list[float]],
        scalars: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        events: list[dict[str, Any]] | None = None,
    ) -> EvaluationContext:
        from openlia.formula.derived import RESERVED_NAMES, compute_derived_scalars

        scalars = scalars or {}
        params = params or {}

        for name in scalars:
            if name in RESERVED_NAMES:
                raise FormulaError(
                    f"reserved derived scalar {name!r} cannot be set in scalars",
                    identifier=name,
                )
        for name in params:
            if name in RESERVED_NAMES:
                raise FormulaError(
                    f"reserved derived scalar {name!r} cannot be set in params",
                    identifier=name,
                )

        values: dict[str, float | bool | str | None] = {}
        # Lowest precedence: params.
        for k, v in params.items():
            values[k] = _coerce_context_value(v)
        # Middle precedence: caller scalars.
        for k, v in scalars.items():
            values[k] = _coerce_context_value(v)
        # Highest precedence: reserved derived scalars (cannot be shadowed).
        derived = compute_derived_scalars(raw_series)
        for k, v in derived.items():
            values[k] = v

        history = {k: list(v) for k, v in raw_series.items()}
        return cls(values=values, history=history, events=list(events or []))


def _coerce_context_value(v: Any) -> float | bool | str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        return v
    return v


# Safety caps -- public constants so tests can import them.
MAX_AST_DEPTH = 64
MAX_NODE_COUNT = 1024
MAX_EVAL_STEPS = 10_000


@dataclass(frozen=True, slots=True)
class _FunctionSpec:
    name: str
    min_args: int
    max_args: int
    needs_history: bool
    impl: Any


FUNCTION_REGISTRY: dict[str, _FunctionSpec] = {}


@dataclass
class FormulaResult:
    """Wrapper for `FormulaEngine.evaluate_safe` calls.

    Direct `FormulaEngine.evaluate` returns the bare value for back-compat
    while still attaching warnings to engine state.
    """

    value: float | bool | str | None
    warnings: list[str] = field(default_factory=list)


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

    def evaluate(
        self,
        expr: str | Expression,
        context: EvaluationContext,
    ) -> float | bool | None:
        if isinstance(expr, str):
            tree = parse(expr)
        else:
            tree = expr
        state = _EvalState()
        result = _eval_node(tree, context, state)
        self.last_warnings = list(state.warnings)
        return _coerce_final(result)

    def evaluate_safe(
        self,
        expr: str | Expression,
        context: EvaluationContext,
    ) -> FormulaResult:
        if isinstance(expr, str):
            tree = parse(expr)
        else:
            tree = expr
        state = _EvalState()
        result = _eval_node(tree, context, state)
        self.last_warnings = list(state.warnings)
        return FormulaResult(value=_coerce_final(result), warnings=list(state.warnings))


@dataclass
class _EvalState:
    steps: int = 0
    warnings: list[str] = field(default_factory=list)


def _step(state: _EvalState) -> None:
    state.steps += 1
    if state.steps > MAX_EVAL_STEPS:
        raise FormulaError(f"evaluation exceeded {MAX_EVAL_STEPS} steps; aborting")


def _coerce_final(value: Any) -> float | bool | str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return value
    raise FormulaError(f"formula produced unsupported result: {type(value).__name__}")


def _require_number(value: Any, *, op: str, node: Expression) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatchError(
            f"operator {op!r} requires numeric operands, got {type(value).__name__}",
            line=node.line,
            col=node.col,
            type_=type(value).__name__,
        )
    return float(value)


def _require_bool(value: Any, *, op: str, node: Expression) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise TypeMismatchError(
            f"operator {op!r} requires boolean operands, got {type(value).__name__}",
            line=node.line,
            col=node.col,
            type_=type(value).__name__,
        )
    return value


def _eval_node(node: Expression, ctx: EvaluationContext, state: _EvalState) -> Any:
    _step(state)

    if isinstance(node, Literal):
        return node.value

    if isinstance(node, Var):
        if node.name not in ctx.values:
            raise UnknownIdentifierError(
                f"undefined variable {node.name!r}",
                line=node.line,
                col=node.col,
                identifier=node.name,
            )
        return ctx.values[node.name]

    if isinstance(node, HistoricalVar):
        series = ctx.history.get(node.name)
        if series is None:
            raise UnknownIdentifierError(
                f"undefined historical series {node.name!r}",
                line=node.line,
                col=node.col,
                identifier=node.name,
            )
        if node.lag >= len(series):
            state.warnings.append(
                f"history for {node.name!r} insufficient: "
                f"needs >= {node.lag + 1}, got {len(series)}"
            )
            return None
        return float(series[-1 - node.lag])

    if isinstance(node, UnaryOp):
        operand = _eval_node(node.operand, ctx, state)
        if node.op == "-":
            num = _require_number(operand, op="-", node=node)
            return None if num is None else -num
        if node.op == "not":
            b = _require_bool(operand, op="not", node=node)
            return None if b is None else (not b)
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
        if cond_b is None:
            return None
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

    # Short-circuit logical operators with null guard.
    if op == "and":
        left = _eval_node(node.left, ctx, state)
        lb = _require_bool(left, op="and", node=node)
        if lb is False:
            return False
        right = _eval_node(node.right, ctx, state)
        rb = _require_bool(right, op="and", node=node)
        if lb is None or rb is None:
            return None
        return lb and rb
    if op == "or":
        left = _eval_node(node.left, ctx, state)
        lb = _require_bool(left, op="or", node=node)
        if lb is True:
            return True
        right = _eval_node(node.right, ctx, state)
        rb = _require_bool(right, op="or", node=node)
        if lb is None or rb is None:
            return None
        return lb or rb

    left = _eval_node(node.left, ctx, state)
    right = _eval_node(node.right, ctx, state)

    if op in {"==", "!="}:
        # Null semantics: null == null -> True; null == x -> False.
        if left is None and right is None:
            return True if op == "==" else False
        if left is None or right is None:
            return False if op == "==" else True
        # String equality.
        if isinstance(left, str) and isinstance(right, str):
            return (left == right) if op == "==" else (left != right)
        # Strict numeric (no bool/number cross-equality).
        if type(left) is not type(right):
            if not (
                isinstance(left, (int, float))
                and isinstance(right, (int, float))
                and not isinstance(left, bool)
                and not isinstance(right, bool)
            ):
                raise TypeMismatchError(
                    f"comparison {op!r} requires matching types, got "
                    f"{type(left).__name__} and {type(right).__name__}",
                    line=node.line,
                    col=node.col,
                    type_=type(left).__name__,
                )
        return (left == right) if op == "==" else (left != right)

    if op in {"<", "<=", ">", ">="}:
        if left is None or right is None:
            return False
        if isinstance(left, str) or isinstance(right, str):
            raise TypeMismatchError(
                f"ordering {op!r} not supported for strings",
                line=node.line,
                col=node.col,
                type_="str",
            )
        ln = _require_number(left, op=op, node=node)
        rn = _require_number(right, op=op, node=node)
        if ln is None or rn is None:
            return False
        return {
            "<": ln < rn,
            "<=": ln <= rn,
            ">": ln > rn,
            ">=": ln >= rn,
        }[op]

    # Arithmetic. Null propagates.
    if left is None or right is None:
        if op in {"+", "-", "*", "/", "%", "**"}:
            return None
    ln = _require_number(left, op=op, node=node)
    rn = _require_number(right, op=op, node=node)
    if ln is None or rn is None:
        return None
    if op == "+":
        return ln + rn
    if op == "-":
        return ln - rn
    if op == "*":
        return ln * rn
    if op == "/":
        if rn == 0.0:
            state.warnings.append("division by zero -> null")
            return None
        return ln / rn
    if op == "%":
        if rn == 0.0:
            state.warnings.append("modulo by zero -> null")
            return None
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
            identifier=node.callee,
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
        if val is None:
            raise TypeMismatchError(
                f"function {node.callee!r} requires numeric args, got null",
                line=node.line,
                col=node.col,
                type_="NoneType",
            )
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            raise TypeMismatchError(
                f"function {node.callee!r} requires numeric args, got {type(val).__name__}",
                line=node.line,
                col=node.col,
                type_=type(val).__name__,
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


def _series_arg(node: Call, ctx: EvaluationContext, *, index: int = 0) -> tuple[str, list[float]]:
    if not node.args or not isinstance(node.args[index], Var):
        raise FormulaError(
            f"function {node.callee!r} requires a bare variable as argument {index + 1}",
            line=node.line,
            col=node.col,
        )
    name = node.args[index].name  # type: ignore[attr-defined]
    series = ctx.history.get(name)
    if series is None:
        raise UnknownIdentifierError(
            f"undefined historical series {name!r}",
            line=node.line,
            col=node.col,
            identifier=name,
        )
    return name, list(series)


# Backward-compat alias used by older internals.
_history_arg = _series_arg


def _int_arg(node: Call, ctx: EvaluationContext, state: _EvalState, index: int) -> int:
    val = _eval_node(node.args[index], ctx, state)
    if val is None:
        raise TypeMismatchError(
            f"function {node.callee!r} requires an integer argument",
            line=node.line,
            col=node.col,
            type_="NoneType",
        )
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TypeMismatchError(
            f"function {node.callee!r} requires an integer argument",
            line=node.line,
            col=node.col,
            type_=type(val).__name__,
        )
    if float(val).is_integer() is False or val < 0:
        raise FormulaError(
            f"function {node.callee!r} requires a non-negative integer",
            line=node.line,
            col=node.col,
        )
    return int(val)


def _number_arg(node: Call, ctx: EvaluationContext, state: _EvalState, index: int) -> float:
    val = _eval_node(node.args[index], ctx, state)
    if val is None:
        raise TypeMismatchError(
            f"function {node.callee!r} requires a numeric argument",
            line=node.line,
            col=node.col,
            type_="NoneType",
        )
    if isinstance(val, bool) or not isinstance(val, (int, float)):
        raise TypeMismatchError(
            f"function {node.callee!r} requires a numeric argument",
            line=node.line,
            col=node.col,
            type_=type(val).__name__,
        )
    return float(val)


def _string_arg(node: Call, ctx: EvaluationContext, state: _EvalState, index: int) -> str:
    val = _eval_node(node.args[index], ctx, state)
    if not isinstance(val, str):
        raise TypeMismatchError(
            f"function {node.callee!r} requires a string argument at position {index + 1}",
            line=node.line,
            col=node.col,
            type_=type(val).__name__,
        )
    return val


def _impl_last(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    if len(node.args) == 1:
        _, series = _series_arg(node, ctx)
        if not series:
            state.warnings.append(f"last({node.callee}): empty history -> null")
            return None
        return float(series[-1])
    name, series = _series_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        state.warnings.append(f"last({name}, {n}): insufficient history -> null")
        return None
    return float(series[-n])


def _impl_pct_change(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    name, series = _series_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n <= 0 or n >= len(series):
        state.warnings.append(f"pct_change({name}, {n}): insufficient history -> null")
        return None
    previous = series[-1 - n]
    current = series[-1]
    if previous == 0:
        state.warnings.append(f"pct_change({name}, {n}): prior value is zero -> null")
        return None
    return (current - previous) / previous * 100.0


def _impl_rolling_mean(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    name, series = _series_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n == 0 or n > len(series):
        state.warnings.append(f"rolling_mean({name}, {n}): insufficient history -> null")
        return None
    window = series[-n:]
    return sum(window) / float(n)


def _impl_lag(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    name, series = _series_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n >= len(series):
        state.warnings.append(f"lag({name}, {n}): insufficient history -> null")
        return None
    return float(series[-1 - n])


def _impl_avg(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    return _impl_rolling_mean(node, ctx, state)


def _impl_slope(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    name, series = _series_arg(node, ctx)
    n = _int_arg(node, ctx, state, 1)
    if n < 2 or n > len(series):
        state.warnings.append(f"slope({name}, {n}): insufficient history -> null")
        return None
    window = series[-n:]
    # Linear regression slope of values vs bar index 0..n-1 (least squares).
    mean_x = (n - 1) / 2.0
    mean_y = sum(window) / n
    num = 0.0
    den = 0.0
    for i, y in enumerate(window):
        dx = i - mean_x
        num += dx * (y - mean_y)
        den += dx * dx
    if den == 0.0:
        state.warnings.append(f"slope({name}, {n}): zero variance in index -> null")
        return None
    return num / den


def _impl_percentile(node: Call, ctx: EvaluationContext, state: _EvalState) -> float | None:
    name, series = _series_arg(node, ctx)
    lookback = _int_arg(node, ctx, state, 1)
    pct = _number_arg(node, ctx, state, 2)
    if lookback <= 0 or lookback > len(series):
        state.warnings.append(
            f"percentile({name}, {lookback}, {pct}): insufficient history -> null"
        )
        return None
    if pct < 0.0 or pct > 100.0:
        raise FormulaError(
            f"percentile pct must be in [0, 100], got {pct}",
            line=node.line,
            col=node.col,
        )
    window = sorted(series[-lookback:])
    if len(window) == 1:
        return float(window[0])
    rank = pct / 100.0 * (len(window) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(window) - 1)
    frac = rank - lo
    return float(window[lo] + (window[hi] - window[lo]) * frac)


def _impl_cross_above(node: Call, ctx: EvaluationContext, state: _EvalState) -> bool | None:
    return _cross(node, ctx, state, above=True)


def _impl_cross_below(node: Call, ctx: EvaluationContext, state: _EvalState) -> bool | None:
    return _cross(node, ctx, state, above=False)


def _cross(node: Call, ctx: EvaluationContext, state: _EvalState, *, above: bool) -> bool | None:
    fast_name, fast_series = _series_arg(node, ctx, index=0)
    slow_name, slow_series = _series_arg(node, ctx, index=1)
    if len(fast_series) < 2 or len(slow_series) < 2:
        state.warnings.append(f"cross({fast_name}, {slow_name}): need 2 bars per series -> null")
        return None
    f_prev, f_now = fast_series[-2], fast_series[-1]
    s_prev, s_now = slow_series[-2], slow_series[-1]
    if above:
        return f_prev <= s_prev and f_now > s_now
    return f_prev >= s_prev and f_now < s_now


_VALID_OPS = {">", "<", ">=", "<=", "==", "!="}


def _impl_consecutive(node: Call, ctx: EvaluationContext, state: _EvalState) -> int:
    _name, series = _series_arg(node, ctx, index=0)
    op = _string_arg(node, ctx, state, 1)
    threshold = _number_arg(node, ctx, state, 2)
    if op not in _VALID_OPS:
        raise FormulaError(
            f"consecutive: op must be one of {sorted(_VALID_OPS)}, got {op!r}",
            line=node.line,
            col=node.col,
        )
    count = 0
    for v in reversed(series):
        match = {
            ">": v > threshold,
            "<": v < threshold,
            ">=": v >= threshold,
            "<=": v <= threshold,
            "==": v == threshold,
            "!=": v != threshold,
        }[op]
        if match:
            count += 1
        else:
            break
    return count


def _impl_days_since(node: Call, ctx: EvaluationContext, state: _EvalState) -> int | None:
    event_type = _string_arg(node, ctx, state, 0)
    matches = [e for e in ctx.events if e.get("event_type") == event_type]
    if not matches:
        state.warnings.append(f"days_since({event_type!r}): no matching event -> null")
        return None
    # Each event must have a numeric `days_ago` field; pick smallest (most recent).
    days_values = [
        e.get("days_ago") for e in matches if isinstance(e.get("days_ago"), (int, float))
    ]
    if not days_values:
        state.warnings.append(f"days_since({event_type!r}): events lack days_ago -> null")
        return None
    return int(min(days_values))


FUNCTION_REGISTRY.update(
    {
        "last": _FunctionSpec("last", 1, 2, True, _impl_last),
        "pct_change": _FunctionSpec("pct_change", 2, 2, True, _impl_pct_change),
        "rolling_mean": _FunctionSpec("rolling_mean", 2, 2, True, _impl_rolling_mean),
        "lag": _FunctionSpec("lag", 2, 2, True, _impl_lag),
        "avg": _FunctionSpec("avg", 2, 2, True, _impl_avg),
        "slope": _FunctionSpec("slope", 2, 2, True, _impl_slope),
        "percentile": _FunctionSpec("percentile", 3, 3, True, _impl_percentile),
        "cross_above": _FunctionSpec("cross_above", 2, 2, True, _impl_cross_above),
        "cross_below": _FunctionSpec("cross_below", 2, 2, True, _impl_cross_below),
        "consecutive": _FunctionSpec("consecutive", 3, 3, True, _impl_consecutive),
        "days_since": _FunctionSpec("days_since", 1, 1, False, _impl_days_since),
    }
)


@dataclass
class ParsedFormula:
    ast: Expression
    identifiers: list[str]
    unknown_identifiers: list[str]
    warnings: list[str]


def parse_formula(
    source: str,
    *,
    known_names: set[str] | frozenset[str] | None = None,
) -> ParsedFormula:
    """Parse a formula string and return its AST plus identifier metadata.

    `unknown_identifiers` lists any referenced identifier (variable, history
    series, or function-call series argument) not present in `known_names`.
    """

    tree = parse(source)
    idents = _collect_identifiers(tree)
    if known_names is None:
        unknown: list[str] = []
    else:
        unknown = sorted({n for n in idents if n not in known_names})
    return ParsedFormula(
        ast=tree,
        identifiers=sorted(idents),
        unknown_identifiers=unknown,
        warnings=[],
    )


def _collect_identifiers(tree: Expression) -> set[str]:
    acc: set[str] = set()
    _walk_idents(tree, acc)
    return acc


def _walk_idents(node: Expression, acc: set[str]) -> None:
    if isinstance(node, Var):
        acc.add(node.name)
        return
    if isinstance(node, HistoricalVar):
        acc.add(node.name)
        return
    if isinstance(node, BinaryOp):
        _walk_idents(node.left, acc)
        _walk_idents(node.right, acc)
        return
    if isinstance(node, UnaryOp):
        _walk_idents(node.operand, acc)
        return
    if isinstance(node, IfElse):
        _walk_idents(node.condition, acc)
        _walk_idents(node.then_branch, acc)
        _walk_idents(node.else_branch, acc)
        return
    if isinstance(node, Call):
        for arg in node.args:
            _walk_idents(arg, acc)
        return
