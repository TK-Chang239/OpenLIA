"""All-Weather (T3) deterministic portfolio-audit classification.

Pure function; no I/O, no LLM. Ports the legacy
``dashboards/all_weather.py`` ``T3_compute`` onto the shared ``risk_math``
primitives: linear risk contributions, per-season coverage, and the gold
gap vs. the Dalio reference. The engine injects the user's portfolio
weights (server-side), then calls this so the model never invents the
computed risk numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from openlia.macro_research.risk_math import (
    DEFAULT_VOLS,
    REFERENCE_ALLOCATION,
    SEASON_ASSETS,
    coverage_for_season,
    gold_gap,
    risk_contributions,
)

Severity = Literal["red", "amber", "green"]


@dataclass(frozen=True)
class AllWeatherClassification:
    severity: Severity
    overall_coverage_label: str
    risk_contributions: dict[str, float]
    reference_risk_contributions: dict[str, float]
    season_coverage: dict[str, str]
    gold_gap: dict[str, float]


def classify_all_weather(weights: dict[str, float]) -> AllWeatherClassification:
    rc_user = risk_contributions(weights=weights, vols=DEFAULT_VOLS)
    rc_ref = risk_contributions(weights=REFERENCE_ALLOCATION, vols=DEFAULT_VOLS)

    season_coverage = {
        season: coverage_for_season(season=season, weights=weights) for season in SEASON_ASSETS
    }
    gap = gold_gap(user_weight=weights.get("gold", 0.0))

    max_rc = max(rc_user.values()) if rc_user else 0.0
    if max_rc > 0.6:
        severity: Severity = "red"
        label = "Concentrated"
    elif max_rc > 0.4:
        severity = "amber"
        label = "Moderately concentrated"
    else:
        severity = "green"
        label = "Balanced"

    return AllWeatherClassification(
        severity=severity,
        overall_coverage_label=label,
        risk_contributions=rc_user,
        reference_risk_contributions=rc_ref,
        season_coverage=season_coverage,
        gold_gap=gap,
    )
