"""Static requirement extraction — parse once, walk the AST, return refs.

Consumers (Plan 18 / Plan 19) feed the returned refs into the data-provider
manifest resolver so scheduled jobs fetch exactly the series and history
depth the formulas need.
"""

from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class RequirementRef:
    name: str
    max_lag: int = 0


# How each history-aware function maps its lookback to max_lag.
# Keys match FUNCTION_REGISTRY names exactly.
_HISTORY_FUNCTIONS: dict[str, int] = {
    # "last": handled separately (1-arg vs 2-arg).
    "pct_change": 0,
    "rolling_mean": -1,  # max_lag = n - 1 (needs n trailing values).
    "lag": 0,
}


def extract_requirements(source: str | Expression) -> list[RequirementRef]:
    tree = parse(source) if isinstance(source, str) else source
    acc: dict[str, int] = {}
    _walk(tree, acc)
    return [RequirementRef(name=name, max_lag=lag) for name, lag in sorted(acc.items())]


def _record(acc: dict[str, int], name: str, lag: int) -> None:
    prior = acc.get(name, -1)
    if lag > prior:
        acc[name] = lag


def _literal_int(node: Expression) -> int | None:
    if isinstance(node, Literal) and isinstance(node.value, (int, float)):
        val = float(node.value)
        if val.is_integer() and val >= 0:
            return int(val)
    return None


def _walk(node: Expression, acc: dict[str, int]) -> None:
    if isinstance(node, Literal):
        return

    if isinstance(node, Var):
        _record(acc, node.name, 0)
        return

    if isinstance(node, HistoricalVar):
        _record(acc, node.name, node.lag)
        return

    if isinstance(node, UnaryOp):
        _walk(node.operand, acc)
        return

    if isinstance(node, BinaryOp):
        _walk(node.left, acc)
        _walk(node.right, acc)
        return

    if isinstance(node, IfElse):
        _walk(node.condition, acc)
        _walk(node.then_branch, acc)
        _walk(node.else_branch, acc)
        return

    if isinstance(node, Call):
        _walk_call(node, acc)
        return

    # Unknown node type — ignore defensively.
    return


def _walk_call(node: Call, acc: dict[str, int]) -> None:
    # If the first argument is a bare Var and the function has a declared
    # lookback, credit the max_lag to that series. Otherwise, walk each arg.
    if node.callee == "last" and len(node.args) >= 1 and isinstance(node.args[0], Var):
        name = node.args[0].name
        if len(node.args) == 2:
            n = _literal_int(node.args[1])
            if n is not None and n > 0:
                _record(acc, name, n - 1)
                return
        _record(acc, name, 0)
        return

    if node.callee in _HISTORY_FUNCTIONS and len(node.args) >= 2 and isinstance(node.args[0], Var):
        name = node.args[0].name
        n = _literal_int(node.args[1])
        if n is None:
            _record(acc, name, 0)
            for arg in node.args:
                _walk(arg, acc)
            return
        offset = _HISTORY_FUNCTIONS[node.callee]
        max_lag = max(0, n + offset)
        _record(acc, name, max_lag)
        return

    # Fall-through: stateless functions (min/max/abs/...), or calls whose first
    # arg isn't a bare Var. Walk every argument to collect any nested refs.
    for arg in node.args:
        _walk(arg, acc)
