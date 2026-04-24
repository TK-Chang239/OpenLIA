"""Composite threat-level aggregation for the 5 PT panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CompositeLevel = Literal["calm", "elevated", "high", "severe", "crisis"]


@dataclass(frozen=True)
class CompositeResult:
    level: CompositeLevel
    score: float
    red_count: int
    mode: str


def _is_red(status: str) -> bool:
    return status in ("red", "dark_red")


def _count_level(red_count: int, threshold: int) -> CompositeLevel:
    if red_count == 0:
        return "calm"
    if red_count < threshold:
        return "elevated"
    if red_count == threshold:
        return "high"
    if red_count == threshold + 1:
        return "severe"
    return "crisis"


def _weighted_level(score: float, thresholds: dict[str, float]) -> CompositeLevel:
    if score < thresholds.get("elevated", 1.0):
        return "calm"
    if score < thresholds.get("high", 2.0):
        return "elevated"
    if score < thresholds.get("severe", 3.0):
        return "high"
    if score < thresholds.get("crisis", 4.0):
        return "severe"
    return "crisis"


def compute_composite(
    panel_statuses: dict[str, str],
    settings: dict[str, Any],
) -> CompositeResult:
    mode = settings.get("mode", "count")
    red_panels = {p: s for p, s in panel_statuses.items() if _is_red(s)}
    red_count = len(red_panels)

    if mode == "weighted":
        weights = settings.get("weights", {})
        score = sum(float(weights.get(p, 0.0)) for p in red_panels)
        level = _weighted_level(score, settings.get("thresholds", {}))
    else:
        threshold = int(settings.get("red_threshold", 2))
        score = float(red_count)
        level = _count_level(red_count, threshold)

    return CompositeResult(level=level, score=score, red_count=red_count, mode=mode)
