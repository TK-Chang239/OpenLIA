"""Test helpers for the formula engine.

Named with the ``_formula_`` prefix per README "Test conventions" to
guarantee uniqueness across the whole test tree.
"""

from __future__ import annotations

from openlia.formula import EvaluationContext


def ctx(**values: float | bool | str) -> EvaluationContext:
    return EvaluationContext(values=dict(values))


def ctx_with_history(
    *,
    values: dict[str, float | bool | str] | None = None,
    history: dict[str, list[float]] | None = None,
) -> EvaluationContext:
    return EvaluationContext(
        values=dict(values or {}),
        history={k: list(v) for k, v in (history or {}).items()},
    )
