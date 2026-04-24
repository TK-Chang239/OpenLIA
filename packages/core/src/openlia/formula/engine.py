"""Evaluation engine. Populated in Task 4.

Exports ``FormulaEngine``, ``EvaluationContext``, ``FormulaError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class FormulaError(Exception):
    """All parse/evaluation failures raise this (or a subclass)."""


@dataclass
class EvaluationContext:
    """Inputs to a formula evaluation.

    ``values``  -- named scalars (numeric or boolean or string).
    ``history`` -- named sequences (chronological, oldest first).
    """

    values: dict[str, float | bool | str] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)


class FormulaEngine:  # pragma: no cover - Task 4
    def evaluate(self, expr, context):
        raise NotImplementedError("FormulaEngine lands in Task 4")
