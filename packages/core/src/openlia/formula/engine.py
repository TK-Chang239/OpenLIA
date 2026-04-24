"""Evaluation engine. Populated in Task 4.

Exports ``FormulaEngine``, ``EvaluationContext``, ``FormulaError``.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    """Inputs to a formula evaluation.

    ``values``  -- named scalars (numeric or boolean or string).
    ``history`` -- named sequences (chronological, oldest first).
    """

    values: dict[str, float | bool | str] = field(default_factory=dict)
    history: dict[str, list[float]] = field(default_factory=dict)


class FormulaEngine:  # pragma: no cover - Task 4
    def evaluate(self, expr, context):
        raise NotImplementedError("FormulaEngine lands in Task 4")
