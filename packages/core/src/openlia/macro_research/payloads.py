"""Typed dashboard payloads. The engine emits one of these per dashboard;
the server returns it verbatim; the React view renders it. Shapes mirror
frontend/src/lib/macro_research/dalio_copy/types.ts. Keep in lockstep.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


# ---------- T3 — All-Weather Audit. Mirrors types.ts:248-341 verbatim. ----------

# T3 donut slices carry their own tone scale (asset-class palette); it is
# unrelated to the shared RAG Tone and must not be widened into it.
T3SliceTone = Literal["accent", "olive", "neutral", "amber", "rust"]


class T3Pill(BaseModel):
    tone: Tone
    label: str


class T3DonutSlice(BaseModel):
    label: str
    pct: float
    tone: T3SliceTone


class T3DonutCard(BaseModel):
    title: str
    slices: list[T3DonutSlice]


class T3CoverageCell(BaseModel):
    title: str
    badgeLabel: str
    badgeTone: Tone
    bodyTone: Tone
    body: str
    bridgeLabel: str
    bridge: str


class T3RiskBar(BaseModel):
    label: str
    pct: float


class T3GoldNeedle(BaseModel):
    label: str
    leftPct: float
    tone: Tone


class T3GoldStat(BaseModel):
    label: str
    value: str
    valueTone: Tone
    note: str


class T3CaveatCard(BaseModel):
    title: str
    body: str


class T3Comparison(BaseModel):
    label: str
    benchmark: T3DonutCard
    reference: T3DonutCard


class T3Coverage(BaseModel):
    label: str
    cells: list[T3CoverageCell]


class T3RiskParity(BaseModel):
    label: str
    intro: str
    benchmarkTitle: str
    benchmarkBars: list[T3RiskBar]
    referenceTitle: str
    referenceBars: list[T3RiskBar]
    mechanism: Prose


class T3Gold(BaseModel):
    label: str
    title: str
    needles: list[T3GoldNeedle]
    stats: list[T3GoldStat]
    rationale: Prose


class T3Caveats(BaseModel):
    label: str
    cards: list[T3CaveatCard]


class T3StressBar(BaseModel):
    label: str
    userPct: float
    refPct: float


class T3StressScenarioRow(BaseModel):
    name: str
    userMedianPct: float
    userP5Pct: float
    refMedianPct: float
    refP5Pct: float
    tone: Tone


class T3StressDistribution(BaseModel):
    title: str
    bars: list[T3StressBar]


class T3StressTest(BaseModel):
    label: str
    intro: str
    distribution: T3StressDistribution
    scenarios: list[T3StressScenarioRow]
    note: str


class AllWeatherData(BaseModel):
    header: DashHeader
    cardSummary: str
    comparison: T3Comparison
    coverage: T3Coverage
    riskParity: T3RiskParity
    stressTest: T3StressTest
    gold: T3Gold
    caveats: T3Caveats
    verdict: Prose
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime


# ---------- T5 — Five Forces. Mirrors types.ts:484-582 verbatim. ----------

# T5 reuses the shared RAG Tone (red/amber/green/blue).


class T5HeaderBadge(BaseModel):
    tone: Tone
    label: str


class T5ForceRow(BaseModel):
    forceLabel: str
    forceSub: str
    pillTone: Tone
    pillLabel: str
    scorePct: int
    scoreTone: Tone
    scoreValue: str
    body: str


class T5LoopArrow(BaseModel):
    fromLabel: str
    toLabel: str


class T5LoopBlock(BaseModel):
    title: str
    arrows: list[T5LoopArrow]
    body: str


class T5ActiveCount(BaseModel):
    countText: str
    countTone: Tone
    title: str
    body: str


class T5SignalCard(BaseModel):
    label: str
    value: str
    unit: str
    note: str


class T5AllocStat(BaseModel):
    label: str
    value: str
    note: str
    highlight: bool


class T5GoldAllocation(BaseModel):
    title: str
    ticks: list[str]
    stats: list[T5AllocStat]
    body: str


class T5Scenario(BaseModel):
    variant: Literal["bull", "bear"]
    title: str
    body: str


class T5Header(BaseModel):
    title: str
    subtitle: str
    badges: list[T5HeaderBadge] = []


class T5Scorecard(BaseModel):
    label: str
    rows: list[T5ForceRow]


class T5Loops(BaseModel):
    label: str
    blocks: list[T5LoopBlock]
    active: T5ActiveCount


class T5Signals(BaseModel):
    label: str
    cards: list[T5SignalCard]


class T5GoldAllocationGroup(BaseModel):
    label: str
    block: T5GoldAllocation


class T5Scenarios(BaseModel):
    label: str
    cards: list[T5Scenario]


class FiveForcesData(BaseModel):
    header: T5Header
    cardSummary: str
    scorecard: T5Scorecard
    loops: T5Loops
    signals: T5Signals
    goldAllocation: T5GoldAllocationGroup
    scenarios: T5Scenarios
    verdict: Prose
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime


# ---------- Summary — cross-framework synthesis. Mirrors types.ts:584-704. ----------

# The Summary surface carries its own RAG+ status scale (six values) shared by
# every Summary sub-model. It is distinct from the four-value Tone the other
# dashboards use; do not widen one into the other. From types.ts:12.
Status = Literal["ok", "warn", "bad", "flat", "info", "acid"]

# T1-T5 framework codes used across the Summary cards, nodes, and edges.
TCode = Literal["T1", "T2", "T3", "T4", "T5"]


class StatTile(BaseModel):
    k: str
    v: str
    status: Status | None = None


class MiniActive(BaseModel):
    active: bool
    index: int | None = None


class ChartPoint(BaseModel):
    year: int
    value: float


class SpotlightChart(BaseModel):
    yLabel: str
    yUnit: str | None = None
    yMin: float | None = None
    yMax: float | None = None
    data: list[ChartPoint]
    current: ChartPoint


class FrameworkStatusStamp(BaseModel):
    label: str
    status: Status


class FrameworkStatusCard(BaseModel):
    tcode: TCode
    slug: str
    acid: bool | None = None
    title: str
    stamp: FrameworkStatusStamp
    verdictLine: str | None = None
    summary: str
    miniVisual: Literal["bars", "quadrant", "ring", "stage", "forces"]
    # list[float] first in the union so a bare array validates as the histogram
    # form rather than coercing into MiniActive.
    miniData: list[float] | MiniActive
    stats: list[StatTile]
    footLabel: str
    spotlight: bool | None = None
    spotlightChart: SpotlightChart | None = None


class RegimeBarSegment(BaseModel):
    k: str
    v: str
    status: Status
    sub: str


class LiaPull(BaseModel):
    k: str
    v: str


class LiaTake(BaseModel):
    label: str
    timestamp: str
    paragraphs: list[str]
    # A fixed 4-tuple (types.ts: [LiaPull, LiaPull, LiaPull, LiaPull]).
    pulls: tuple[LiaPull, LiaPull, LiaPull, LiaPull]


class DepMapNode(BaseModel):
    id: str
    tcode: TCode
    name: str
    status: Status
    statusLabel: str
    position: Literal["left-top", "left-mid", "left-bot", "center", "right"]


class DepMapEdge(BaseModel):
    # `from` is a Python keyword; the field is `from_` and serializes to the
    # JSON key `from` via the alias. populate_by_name lets validation accept
    # either key.
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    label: str
    variant: Literal["solid", "dashed", "accent"]


class CascadeStep(BaseModel):
    badge: str
    title: str
    body: str
    target: bool | None = None


class ConsolidatedTrigger(BaseModel):
    status: Status
    name: str
    source: str
    desc: str
    fromTabs: str


class SummaryHeroStat(BaseModel):
    k: str
    v: str
    status: Status


class SummaryHero(BaseModel):
    eyebrow: str
    eyebrowStrong: str | None = None
    headline: str
    headlineAccent: str
    lede: str
    stats: list[SummaryHeroStat]


class SummaryRegimeBar(BaseModel):
    label: str
    subLabel: str
    segments: list[RegimeBarSegment]


class SummaryFrameworkStatus(BaseModel):
    label: str
    subLabel: str
    cards: list[FrameworkStatusCard]


class SummaryDepMap(BaseModel):
    label: str
    subLabel: str
    sub: str
    nodes: list[DepMapNode]
    edges: list[DepMapEdge]


class SummaryCascade(BaseModel):
    label: str
    subLabel: str
    sub: str
    row1: list[CascadeStep]
    row2: list[CascadeStep]


class SummaryWatchlist(BaseModel):
    label: str
    subLabel: str
    triggers: list[ConsolidatedTrigger]


class SummaryData(BaseModel):
    hero: SummaryHero
    liaTake: LiaTake
    regimeBar: SummaryRegimeBar
    frameworkStatus: SummaryFrameworkStatus
    depMap: SummaryDepMap
    cascade: SummaryCascade
    watchlist: SummaryWatchlist
    sources: str
    # Redesign additions (not in types.ts): provenance + freshness.
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime
