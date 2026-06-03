"""Four Seasons (T2) deterministic classification. Pure function; no I/O, no LLM.

Ported from the legacy dashboards/four_seasons.py T3_compute: four
already-fetched scalar indicators map to a Dalio economic season and an
overall RAG severity via fixed thresholds, plus a best/worst asset playbook.
Adds a deterministic quadrant-marker placement so the engine never invents
the marker coordinates. The engine gathers the inputs (connector tools /
web_search), then calls this so the model never invents the computed season.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Tone = Literal["red", "amber", "green"]

# Best/worst asset mapping per clean season (ported verbatim from the legacy
# FourSeasonsDashboard._playbook).
_PLAYBOOK: dict[str, dict[str, list[str]]] = {
    "Spring": {"best": ["equities"], "worst": ["commodities"]},
    "Summer": {"best": ["commodities", "TIPS"], "worst": ["long nominal bonds"]},
    "Autumn": {"best": ["gold", "real assets"], "worst": ["equities", "long bonds"]},
    "Winter": {"best": ["long bonds", "cash"], "worst": ["commodities"]},
}


@dataclass(frozen=True)
class SeasonsInputs:
    pmi: float
    gdp_yoy: float
    cpi_yoy: float
    credit_spread: float


@dataclass(frozen=True)
class SeasonsClassification:
    season: str
    severity: Tone
    confidence: str
    growth_axis: str
    inflation_axis: str
    marker_x_pct: int
    marker_y_pct: int
    best_assets: list[str] = field(default_factory=list)
    worst_assets: list[str] = field(default_factory=list)


def _clamp_pct(v: float) -> int:
    return max(0, min(100, round(v)))


def classify_four_seasons(inputs: SeasonsInputs) -> SeasonsClassification:
    pmi = inputs.pmi
    gdp = inputs.gdp_yoy
    cpi = inputs.cpi_yoy

    growth_rising = gdp > 1.0 and pmi >= 50
    growth_falling = gdp < 1.0 and pmi < 50
    inflation_rising = cpi > 3.0
    inflation_falling = cpi <= 2.0

    if growth_rising and inflation_falling:
        season = "Spring"
        severity: Tone = "green"
    elif growth_rising and inflation_rising:
        season = "Summer"
        severity = "amber"
    elif growth_falling and inflation_rising:
        season = "Autumn"
        severity = "red"
    elif growth_falling and inflation_falling:
        season = "Winter"
        severity = "amber"
    else:
        season = "Transitioning"
        severity = "amber"

    confidence = "clear"
    if not (growth_rising or growth_falling) or not (inflation_rising or inflation_falling):
        confidence = "mixed"
    if season == "Transitioning":
        confidence = "transitioning"

    growth_axis = "rising" if growth_rising else ("falling" if growth_falling else "flat")
    inflation_axis = (
        "rising" if inflation_rising else ("falling" if inflation_falling else "steady")
    )

    playbook = _PLAYBOOK.get(season, {"best": [], "worst": []})

    return SeasonsClassification(
        season=season,
        severity=severity,
        confidence=confidence,
        growth_axis=growth_axis,
        inflation_axis=inflation_axis,
        # Growth axis: PMI 45 -> 0, 55 -> 100. Inflation axis: CPI 1% -> 0, 5% -> 100.
        marker_x_pct=_clamp_pct((pmi - 45.0) * 10.0),
        marker_y_pct=_clamp_pct((cpi - 1.0) * 25.0),
        best_assets=list(playbook["best"]),
        worst_assets=list(playbook["worst"]),
    )
