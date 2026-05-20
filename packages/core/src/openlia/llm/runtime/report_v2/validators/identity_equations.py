"""Declarative identity-equation spec + generic evaluator (PR 4).

Templates declare their identity equations as a list of `IdentityEquationSpec`
records. Each equation says: *given fact `lhs_a` and fact `lhs_b`, the result
of `lhs_a OP lhs_b` should equal fact `rhs` within `tolerance_pct`*.

Supported operations: `mul`, `div`, `add`, `sub`. More elaborate equations
(e.g. percent-difference reconciliation, categorical coherence checks) stay
in Python until a second template asks for them.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from openlia.llm.runtime.report_v2.types import Fact

EquationOp = Literal["mul", "div", "add", "sub"]


class IdentityEquationSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    lhs_a: str
    op: EquationOp
    lhs_b: str
    rhs: str
    tolerance_pct: float = 2.0


class EquationFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    equation_name: str
    failure_type: Literal["identity_equation_violation"] = "identity_equation_violation"
    fact_name: str  # `rhs` field name, since that's the one that disagrees
    expected_value: float
    actual_value: float
    tolerance_pct: float
    detail: str


def _apply(op: EquationOp, a: float, b: float) -> float:
    if op == "mul":
        return a * b
    if op == "div":
        return a / b
    if op == "add":
        return a + b
    if op == "sub":
        return a - b
    raise ValueError(f"unsupported equation op {op!r}")


def _facts_get_numeric(facts: dict[str, Fact], name: str) -> float | None:
    fact = facts.get(name)
    if fact is None or fact.value is None:
        return None
    try:
        return float(fact.value)
    except (TypeError, ValueError):
        return None


def _within_pct(expected: float, actual: float, tolerance_pct: float) -> bool:
    if expected == 0:
        return abs(actual) <= tolerance_pct / 100.0
    return abs((expected - actual) / expected) <= tolerance_pct / 100.0


def evaluate_equations(
    equations: list[IdentityEquationSpec] | tuple[IdentityEquationSpec, ...],
    facts: dict[str, Fact],
) -> list[EquationFailure]:
    """Apply every equation to the facts dict; return violations.

    Equations whose operands are missing or non-numeric are silently skipped.
    """
    failures: list[EquationFailure] = []
    for eq in equations:
        a = _facts_get_numeric(facts, eq.lhs_a)
        b = _facts_get_numeric(facts, eq.lhs_b)
        c = _facts_get_numeric(facts, eq.rhs)
        if a is None or b is None or c is None:
            continue
        try:
            expected = _apply(eq.op, a, b)
        except ZeroDivisionError:
            continue
        if not _within_pct(expected, c, eq.tolerance_pct):
            failures.append(
                EquationFailure(
                    equation_name=eq.name,
                    fact_name=eq.rhs,
                    expected_value=expected,
                    actual_value=c,
                    tolerance_pct=eq.tolerance_pct,
                    detail=(
                        f"{eq.lhs_a} {eq.op} {eq.lhs_b} = {expected:.4g} "
                        f"disagrees with {eq.rhs} = {c:.4g}"
                    ),
                )
            )
    return failures
