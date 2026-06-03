"""Typed dashboard payloads. The engine emits one of these per dashboard;
the server returns it verbatim; the React view renders it. Shapes mirror
frontend/src/lib/macro_research/dalio_copy/types.ts. Keep in lockstep.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel

# T1Tone matches types.ts: "red" | "amber" | "green" | "blue"
Tone = Literal["red", "amber", "green", "blue"]


class Provenance(StrEnum):
    LIVE = "live"
    COMPUTED = "computed"
    REFERENCE = "reference"


class Pill(BaseModel):
    tone: Tone
    label: str


class DashHeader(BaseModel):
    title: str
    subtitle: str
    pills: list[Pill] = []


class ScoreRow(BaseModel):
    name: str
    sub: str
    current: str
    currentTone: Tone
    currentMeta: str
    threshold: str
    status: str
    statusTone: Tone
    fillPct: int
    fillTone: Tone


class Prose(BaseModel):
    title: str
    body: str


class TonedProse(Prose):
    tone: Tone


class PolicyCard(BaseModel):
    label: str
    value: str
    valueTone: Tone
    unit: str
    note: str


class WatchRow(BaseModel):
    tone: Tone
    name: str
    body: str


class DebtCycleData(BaseModel):
    header: DashHeader
    cardSummary: str
    scorecard: dict[str, Any]
    phaseBox: TonedProse
    analogPair: dict[str, Prose]
    policySpace: dict[str, Any]
    assetThesis: dict[str, Prose]
    watchlist: dict[str, Any]
    verdict: TonedProse
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime
