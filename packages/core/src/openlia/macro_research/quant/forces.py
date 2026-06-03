"""Five Forces (T5) deterministic classification. Pure function; no I/O, no LLM.

Ports the legacy ``dashboards/five_forces.py`` ``T3_compute``: five 0-10
force-intensity scores (debt/money, political, geopolitical, technology,
natural) collapse to an active-force count (a force is "active" at score >= 7),
a bucket, and an overall RAG severity. Two of the five inputs are seeded from
other dashboards' cached classifications (F1 from debt_cycle, F3 from
world_order); the engine researches the rest. The engine calls this so the
model never invents the computed count or bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["red", "amber", "green"]

_ACTIVE_THRESHOLD = 7.0


@dataclass(frozen=True)
class ForceScores:
    debt_money: float
    political: float
    geopolitical: float
    technology: float
    natural: float


@dataclass(frozen=True)
class ForcesClassification:
    force_scores: dict[str, float]
    active_force_count: int
    bucket: str
    severity: Severity


def classify_five_forces(scores: ForceScores) -> ForcesClassification:
    force_scores: dict[str, float] = {
        "debt_money": scores.debt_money,
        "political": scores.political,
        "geopolitical": scores.geopolitical,
        "technology": scores.technology,
        "natural": scores.natural,
    }
    active = sum(1 for score in force_scores.values() if score >= _ACTIVE_THRESHOLD)

    if active <= 1:
        bucket = "Normal"
        severity: Severity = "green"
    elif active <= 3:
        bucket = "Elevated"
        severity = "amber"
    else:
        bucket = "Historical turning point zone"
        severity = "red"

    return ForcesClassification(
        force_scores=force_scores,
        active_force_count=active,
        bucket=bucket,
        severity=severity,
    )
