"""Static requirement extraction. Populated in Task 8."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RequirementRef:
    """Static reference to a variable plus its maximum historical lag (if any)."""

    name: str
    max_lag: int = 0


def extract_requirements(source: str) -> list[RequirementRef]:  # pragma: no cover - Task 8
    raise NotImplementedError("extract_requirements lands in Task 8")
