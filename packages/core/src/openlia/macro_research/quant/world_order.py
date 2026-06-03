"""World Order (T4) deterministic classification. Pure function; no I/O, no LLM.

Parallels classify_debt_cycle: four already-fetched scalar indicators map to a
Dalio empire-cycle stage and an overall RAG severity via fixed thresholds. The
engine gathers the inputs (connector tools / web_search), then calls this so the
model never invents the computed stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Tone = Literal["red", "amber", "green"]

_RESERVE_SHARE_WARN = 60.0
_RESERVE_SHARE_CRIT = 55.0
_CB_GOLD_WARN = 400.0
_CB_GOLD_CRIT = 800.0
_TREASURY_TREND_WARN = 0.0
_TREASURY_TREND_CRIT = -2.0
_DXY_WARN = 102.0
_DXY_CRIT = 98.0


@dataclass(frozen=True)
class WorldOrderInputs:
    usd_reserve_share: float
    cb_gold_purchases: float
    foreign_treasury_trend: float
    dxy: float


@dataclass(frozen=True)
class WorldOrderClassification:
    stage: str
    severity: Tone
    indicator_statuses: dict[str, Tone]
    red_count: int
    amber_count: int


def _bucket_low(value: float, warn: float, crit: float) -> Tone:  # lower = worse
    if value <= crit:
        return "red"
    if value <= warn:
        return "amber"
    return "green"


def _bucket_high(value: float, warn: float, crit: float) -> Tone:  # higher = worse
    if value >= crit:
        return "red"
    if value >= warn:
        return "amber"
    return "green"


def classify_world_order(inputs: WorldOrderInputs) -> WorldOrderClassification:
    statuses: dict[str, Tone] = {
        "usd_reserve_share": _bucket_low(
            inputs.usd_reserve_share, _RESERVE_SHARE_WARN, _RESERVE_SHARE_CRIT
        ),
        "cb_gold_purchases": _bucket_high(inputs.cb_gold_purchases, _CB_GOLD_WARN, _CB_GOLD_CRIT),
        "foreign_treasury_trend": _bucket_low(
            inputs.foreign_treasury_trend, _TREASURY_TREND_WARN, _TREASURY_TREND_CRIT
        ),
        "dxy": _bucket_low(inputs.dxy, _DXY_WARN, _DXY_CRIT),
    }
    red = sum(1 for s in statuses.values() if s == "red")
    amber = sum(1 for s in statuses.values() if s == "amber")
    if red >= 2:
        stage, severity = "Late (Stage 5-6)", "red"
    elif red == 1 or amber >= 2:
        stage, severity = "Mid (Stage 4-5)", "amber"
    else:
        stage, severity = "Early (Stage 3)", "green"
    return WorldOrderClassification(
        stage=stage,
        severity=severity,
        indicator_statuses=statuses,
        red_count=red,
        amber_count=amber,
    )
