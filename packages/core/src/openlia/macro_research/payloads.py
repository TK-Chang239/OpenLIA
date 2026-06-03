"""Typed dashboard payloads. The engine emits one of these per dashboard;
the server returns it verbatim; the React view renders it. Shapes mirror
frontend/src/lib/macro_research/dalio_copy/types.ts. Keep in lockstep.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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


class Scorecard(BaseModel):
    rows: list[ScoreRow]


class PolicySpace(BaseModel):
    cards: list[PolicyCard]


class Watchlist(BaseModel):
    rows: list[WatchRow]


class AnalogPair(BaseModel):
    analog: Prose
    timeToConstraint: Prose


class AssetThesis(BaseModel):
    gold: Prose
    longBond: Prose


class DebtCycleData(BaseModel):
    header: DashHeader
    cardSummary: str
    scorecard: Scorecard
    phaseBox: TonedProse
    analogPair: AnalogPair
    policySpace: PolicySpace
    assetThesis: AssetThesis
    watchlist: Watchlist
    verdict: TonedProse
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime


# ---------- T4 — World Order. Mirrors types.ts:343-482 verbatim. ----------


class T4Pill(BaseModel):
    tone: Tone
    label: str


class T4ScorecardRow(BaseModel):
    name: str
    sub: str
    current: str
    currentTone: Tone
    currentMeta: str
    fillPct: int
    fillTone: Tone
    trend: str
    signalLabel: str
    signalTone: Tone


class T4ReserveSeries(BaseModel):
    label: str
    values: list[float]
    isPrimary: bool = False


class T4ReserveChart(BaseModel):
    title: str
    years: list[int]
    series: list[T4ReserveSeries]


class T4StageCell(BaseModel):
    num: str
    name: str
    range: str
    state: Literal["past", "active", "future"]
    weight: int | None = None


class T4DalioQuote(BaseModel):
    title: str
    body: str
    attribution: str
    tone: Tone


class T4MarkerRow(BaseModel):
    tone: Tone
    pillLabel: str
    leadPhrase: str
    body: str


class T4AnalogCell(BaseModel):
    era: str
    tone: Tone
    body: str


class T4ShiftAssessment(BaseModel):
    title: str
    body: str


class T4GoldRangeStat(BaseModel):
    label: str
    value: str
    highlight: bool


class T4CurrencyRow(BaseModel):
    name: str
    badgeLabel: str
    badgeTone: Tone
    body: str


class T4ProseCard(BaseModel):
    title: str
    body: str


class T4Scorecard(BaseModel):
    label: str
    rows: list[T4ScorecardRow]


class T4EmpireCycle(BaseModel):
    label: str
    stripTitle: str
    stages: list[T4StageCell]
    quote: T4DalioQuote
    markersTitle: str
    markers: list[T4MarkerRow]


class T4Analogs(BaseModel):
    label: str
    cells: list[T4AnalogCell]


class T4WealthShift(BaseModel):
    label: str
    intro: str
    rows: list[T4MarkerRow]
    assessment: T4ShiftAssessment


class T4GoldRange(BaseModel):
    title: str
    stats: list[T4GoldRangeStat]
    body: str


class T4Currency(BaseModel):
    title: str
    rows: list[T4CurrencyRow]


class T4SovereignBondPair(BaseModel):
    left: T4ProseCard
    right: T4ProseCard


class T4SovereignBond(BaseModel):
    title: str
    intro: str
    pair: T4SovereignBondPair


class T4Investment(BaseModel):
    label: str
    goldRange: T4GoldRange
    currency: T4Currency
    sovereignBond: T4SovereignBond


class WorldOrderData(BaseModel):
    header: DashHeader
    cardSummary: str
    scorecard: T4Scorecard
    reserveChart: T4ReserveChart
    empireCycle: T4EmpireCycle
    analogs: T4Analogs
    wealthShift: T4WealthShift
    investment: T4Investment
    verdict: TonedProse
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime


# ---------- T2 — Four Seasons. Mirrors types.ts:129-246 verbatim. ----------

# T2 carries its own tone scale with an extra "purple" value; do not widen the
# shared Tone, which DashHeader and the other dashboards depend on.
T2Tone = Literal["red", "amber", "green", "blue", "purple"]
T2Direction = Literal["up", "down", "flat"]


class T2Pill(BaseModel):
    tone: T2Tone
    label: str


class T2Header(BaseModel):
    title: str
    subtitle: str
    pills: list[T2Pill] = []


class T2ScorecardRow(BaseModel):
    name: str
    sub: str
    fillPct: int
    fillTone: T2Tone
    current: str
    currentTone: T2Tone
    currentMeta: str
    trend: str
    axisLabel: str
    axisTone: T2Tone
    direction: T2Direction
    directionLabel: str
    directionTone: T2Tone


class T2QuadrantSeason(BaseModel):
    name: str
    sub: str
    pillLabel: str
    tone: T2Tone


class T2QuadrantMarker(BaseModel):
    label: str
    xPct: int
    yPct: int
    variant: Literal["now", "prev"]
    tone: T2Tone


class T2VerdictSide(BaseModel):
    label: str
    value: str
    valueTone: T2Tone
    note: str


class T2ProseCard(BaseModel):
    title: str
    body: str


class T2AssetCard(BaseModel):
    tone: T2Tone
    label: str
    posture: str
    body: str


class T2Note(BaseModel):
    title: str
    body: str


class T2Scorecard(BaseModel):
    rows: list[T2ScorecardRow]


class T2QuadrantSeasons(BaseModel):
    tl: T2QuadrantSeason
    tr: T2QuadrantSeason
    bl: T2QuadrantSeason
    br: T2QuadrantSeason


class T2Quadrant(BaseModel):
    seasons: T2QuadrantSeasons
    markers: list[T2QuadrantMarker]


class T2Verdict(BaseModel):
    title: str
    body: str
    sideCards: list[T2VerdictSide]


class T2Parallels(BaseModel):
    cards: list[T2ProseCard]


class T2KeyIndicator(BaseModel):
    title: str
    body: str


class T2TransitionRisk(BaseModel):
    intro: str
    bull: T2ProseCard
    bear: T2ProseCard
    keyIndicator: T2KeyIndicator


class T2AssetPlaybook(BaseModel):
    cards: list[T2AssetCard]


class FourSeasonsData(BaseModel):
    header: T2Header
    cardSummary: str
    scorecard: T2Scorecard
    quadrant: T2Quadrant
    verdict: T2Verdict
    parallels: T2Parallels
    transitionRisk: T2TransitionRisk
    assetPlaybook: T2AssetPlaybook
    notes: list[T2Note]
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime
