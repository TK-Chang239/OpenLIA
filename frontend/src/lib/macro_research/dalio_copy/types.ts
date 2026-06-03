/**
 * Dalio macro dashboard type system. Each per-dashboard shape is the
 * eventual API contract — fallback constants in `<slug>.ts` match
 * these types verbatim, and once the backend produces the same shapes
 * the views consume them unchanged.
 *
 * To wire backend: replace `?? FALLBACK` in each view with the result
 * of `getDashboard(slug)` once the API returns the matching shape, and
 * delete the fallback file.
 */

export type Status = "ok" | "warn" | "bad" | "flat" | "info" | "acid";

export interface BadgeStatus {
  label: string;
  status: Status;
}

export interface DashboardHeader {
  tcode: "T1" | "T2" | "T3" | "T4" | "T5";
  title: string;
  subtitle: string;
  livePill?: string;
  refreshLabel?: string;
}

export interface HeroStats {
  k: string;
  v: string;
  status: Status;
}

export interface Hero {
  eyebrow: string;
  eyebrowStatus: Status;
  headline: string;
  headlineAccent?: string;
  lede: string;
  secondaryLede?: string;
  stats: HeroStats[];
}

export interface SynthesisVerdict {
  label: string;
  badge: string;
  meta: string;
  headline: string;
  body: string;
  tags: { label: string; href?: string }[];
}

export interface SourcesLine {
  text: string;
}

/* ---------- T1 — Debt Cycle ---------- */

export type T1Tone = "red" | "amber" | "green" | "blue";

export interface T1Pill {
  tone: T1Tone;
  label: string;
}

export interface T1ScorecardRow {
  name: string;
  sub: string;
  current: string;
  currentTone: T1Tone;
  currentMeta: string;
  threshold: string;
  status: string;
  statusTone: T1Tone;
  fillPct: number;
  fillTone: T1Tone;
}

export interface T1PolicyCard {
  label: string;
  value: string;
  valueTone: T1Tone;
  unit: string;
  note: string;
}

export interface T1WatchRow {
  tone: T1Tone;
  name: string;
  body: string;
}

export interface DebtCycleData {
  header: {
    title: string;
    subtitle: string;
    pills: T1Pill[];
  };
  cardSummary: string;
  scorecard: {
    rows: T1ScorecardRow[];
  };
  phaseBox: {
    title: string;
    body: string;
    tone: T1Tone;
  };
  analogPair: {
    analog: { title: string; body: string };
    timeToConstraint: { title: string; body: string };
  };
  policySpace: {
    cards: T1PolicyCard[];
  };
  assetThesis: {
    gold: { title: string; body: string };
    longBond: { title: string; body: string };
  };
  watchlist: {
    rows: T1WatchRow[];
  };
  verdict: {
    title: string;
    body: string;
    tone: T1Tone;
  };
  sources: string;
}

/* ---------- T2 — Four Seasons ---------- */

/** Shared by T2 and the SummaryView regime quadrant. SummaryView uses
 *  the older `QuadrantSeason`/`QuadrantMarker` shape; the T2-prefixed
 *  shapes below are tone-driven equivalents used by the rebuilt T2
 *  diagnostic. */
export interface QuadrantMarker {
  label: string;
  xPct: number;
  yPct: number;
  variant: "now" | "prev";
}

export interface QuadrantSeason {
  name: string;
  sub: string;
  pillLabel: string;
  pillStatus: Status;
}

export type T2Tone = "red" | "amber" | "green" | "blue" | "purple";

export interface T2Pill {
  tone: T2Tone;
  label: string;
}

export type T2Direction = "up" | "down" | "flat";

export interface T2ScorecardRow {
  name: string;
  sub: string;
  fillPct: number;
  fillTone: T2Tone;
  current: string;
  currentTone: T2Tone;
  currentMeta: string;
  trend: string;
  axisLabel: string;
  axisTone: T2Tone;
  direction: T2Direction;
  directionLabel: string;
  directionTone: T2Tone;
}

export interface T2QuadrantSeason {
  name: string;
  sub: string;
  pillLabel: string;
  tone: T2Tone;
}

export interface T2QuadrantMarker {
  label: string;
  xPct: number;
  yPct: number;
  variant: "now" | "prev";
  tone: T2Tone;
}

export interface T2VerdictSide {
  label: string;
  value: string;
  valueTone: T2Tone;
  note: string;
}

export interface T2ProseCard {
  title: string;
  body: string;
}

export interface T2AssetCard {
  tone: T2Tone;
  label: string;
  posture: string;
  body: string;
}

export interface T2Note {
  title: string;
  body: string;
}

export interface FourSeasonsData {
  header: {
    title: string;
    subtitle: string;
    pills: T2Pill[];
  };
  cardSummary: string;
  scorecard: {
    rows: T2ScorecardRow[];
  };
  quadrant: {
    seasons: { tl: T2QuadrantSeason; tr: T2QuadrantSeason; bl: T2QuadrantSeason; br: T2QuadrantSeason };
    markers: T2QuadrantMarker[];
  };
  verdict: {
    title: string;
    body: string;
    sideCards: T2VerdictSide[];
  };
  parallels: {
    cards: T2ProseCard[];
  };
  transitionRisk: {
    intro: string;
    bull: T2ProseCard;
    bear: T2ProseCard;
    keyIndicator: { title: string; body: string };
  };
  assetPlaybook: {
    cards: T2AssetCard[];
  };
  notes: T2Note[];
  sources: string;
}

/* ---------- T3 — All-Weather Audit ---------- */

export type T3Tone = "red" | "amber" | "green" | "blue";

export interface T3Pill {
  tone: T3Tone;
  label: string;
}

export type T3SliceTone = "accent" | "olive" | "neutral" | "amber" | "rust";

export interface T3DonutSlice {
  label: string;
  pct: number;
  tone: T3SliceTone;
}

export interface T3DonutCard {
  title: string;
  slices: T3DonutSlice[];
}

export interface T3CoverageCell {
  title: string;
  badgeLabel: string;
  badgeTone: T3Tone;
  bodyTone: T3Tone;
  body: string;
  bridgeLabel: string;
  bridge: string;
}

export interface T3RiskBar {
  label: string;
  pct: number;
}

export interface T3GoldNeedle {
  label: string;
  leftPct: number;
  tone: T3Tone;
}

export interface T3GoldStat {
  label: string;
  value: string;
  valueTone: T3Tone;
  note: string;
}

export interface T3CaveatCard {
  title: string;
  body: string;
}

export interface T3StressBar {
  label: string;
  userPct: number;
  refPct: number;
}

export interface T3StressScenarioRow {
  name: string;
  userMedianPct: number;
  userP5Pct: number;
  refMedianPct: number;
  refP5Pct: number;
  tone: T3Tone;
}

export interface T3StressDistribution {
  title: string;
  bars: T3StressBar[];
}

export interface T3StressTest {
  label: string;
  intro: string;
  distribution: T3StressDistribution;
  scenarios: T3StressScenarioRow[];
  note: string;
}

export interface AllWeatherData {
  header: {
    title: string;
    subtitle: string;
    pills: T3Pill[];
  };
  cardSummary: string;
  comparison: {
    label: string;
    benchmark: T3DonutCard;
    reference: T3DonutCard;
  };
  coverage: {
    label: string;
    cells: T3CoverageCell[];
  };
  riskParity: {
    label: string;
    intro: string;
    benchmarkTitle: string;
    benchmarkBars: T3RiskBar[];
    referenceTitle: string;
    referenceBars: T3RiskBar[];
    mechanism: { title: string; body: string };
  };
  stressTest: T3StressTest;
  gold: {
    label: string;
    title: string;
    needles: T3GoldNeedle[];
    stats: T3GoldStat[];
    rationale: { title: string; body: string };
  };
  caveats: {
    label: string;
    cards: T3CaveatCard[];
  };
  verdict: { title: string; body: string };
  sources: string;
}

/* ---------- T4 — World Order ---------- */

export type T4Tone = "red" | "amber" | "green" | "blue";

export interface T4Pill {
  tone: T4Tone;
  label: string;
}

export interface T4ScorecardRow {
  name: string;
  sub: string;
  current: string;
  currentTone: T4Tone;
  currentMeta: string;
  fillPct: number;
  fillTone: T4Tone;
  trend: string;
  signalLabel: string;
  signalTone: T4Tone;
}

export interface T4ReserveSeries {
  label: string;
  values: number[];
  isPrimary?: boolean;
}

export interface T4ReserveChart {
  title: string;
  years: number[];
  series: T4ReserveSeries[];
}

export interface T4StageCell {
  num: string;
  name: string;
  range: string;
  state: "past" | "active" | "future";
  /** 1..n alpha ramp index for past cells (later = heavier). */
  weight?: number;
}

export interface T4DalioQuote {
  title: string;
  body: string;
  attribution: string;
  tone: T4Tone;
}

export interface T4MarkerRow {
  tone: T4Tone;
  pillLabel: string;
  leadPhrase: string;
  body: string;
}

export interface T4AnalogCell {
  era: string;
  tone: T4Tone;
  body: string;
}

export interface T4ShiftAssessment {
  title: string;
  body: string;
}

export interface T4GoldRangeStat {
  label: string;
  value: string;
  highlight: boolean;
}

export interface T4CurrencyRow {
  name: string;
  badgeLabel: string;
  badgeTone: T4Tone;
  body: string;
}

export interface T4ProseCard {
  title: string;
  body: string;
}

export interface WorldOrderData {
  header: {
    title: string;
    subtitle: string;
    pills: T4Pill[];
  };
  cardSummary: string;
  scorecard: {
    label: string;
    rows: T4ScorecardRow[];
  };
  reserveChart: T4ReserveChart;
  empireCycle: {
    label: string;
    stripTitle: string;
    stages: T4StageCell[];
    quote: T4DalioQuote;
    markersTitle: string;
    markers: T4MarkerRow[];
  };
  analogs: {
    label: string;
    cells: T4AnalogCell[];
  };
  wealthShift: {
    label: string;
    intro: string;
    rows: T4MarkerRow[];
    assessment: T4ShiftAssessment;
  };
  investment: {
    label: string;
    goldRange: {
      title: string;
      stats: T4GoldRangeStat[];
      body: string;
    };
    currency: {
      title: string;
      rows: T4CurrencyRow[];
    };
    sovereignBond: {
      title: string;
      intro: string;
      pair: { left: T4ProseCard; right: T4ProseCard };
    };
  };
  verdict: {
    title: string;
    body: string;
    tone: T4Tone;
  };
  sources: string;
}

/* ---------- T5 — Five Forces ---------- */

export type T5Tone = "red" | "amber" | "green" | "blue";

export interface T5HeaderBadge {
  tone: T5Tone;
  label: string;
}

export interface T5ForceRow {
  forceLabel: string;
  forceSub: string;
  pillTone: T5Tone;
  pillLabel: string;
  scorePct: number;
  scoreTone: T5Tone;
  scoreValue: string;
  body: string;
}

export interface T5LoopArrow {
  fromLabel: string;
  toLabel: string;
}

export interface T5LoopBlock {
  title: string;
  arrows: T5LoopArrow[];
  body: string;
}

export interface T5ActiveCount {
  countText: string;
  countTone: T5Tone;
  title: string;
  body: string;
}

export interface T5SignalCard {
  label: string;
  value: string;
  unit: string;
  note: string;
}

export interface T5AllocStat {
  label: string;
  value: string;
  note: string;
  highlight: boolean;
}

export interface T5GoldAllocation {
  title: string;
  ticks: string[];
  stats: T5AllocStat[];
  body: string;
}

export interface T5Scenario {
  variant: "bull" | "bear";
  title: string;
  body: string;
}

export interface FiveForcesData {
  header: {
    title: string;
    subtitle: string;
    badges: T5HeaderBadge[];
  };
  cardSummary: string;
  scorecard: {
    label: string;
    rows: T5ForceRow[];
  };
  loops: {
    label: string;
    blocks: T5LoopBlock[];
    active: T5ActiveCount;
  };
  signals: {
    label: string;
    cards: T5SignalCard[];
  };
  goldAllocation: {
    label: string;
    block: T5GoldAllocation;
  };
  scenarios: {
    label: string;
    cards: T5Scenario[];
  };
  verdict: {
    title: string;
    body: string;
  };
  sources: string;
}

/* ---------- Macro Research Summary ---------- */

export interface FrameworkStatusCard {
  tcode: "T1" | "T2" | "T3" | "T4" | "T5";
  slug: string;
  acid?: boolean;
  title: string;
  stamp: { label: string; status: Status };
  /** Long verdict line shown on the spotlight card; falls back to `summary`. */
  verdictLine?: string;
  summary: string;
  miniVisual: "bars" | "quadrant" | "ring" | "stage" | "forces";
  miniData: number[] | { active: boolean; index?: number };
  /** 3 small stat tiles shown inside each card. */
  stats: { k: string; v: string; status?: Status }[];
  /** Footer label, e.g. "Open T1 dashboard" or "Conv 62". */
  footLabel: string;
  /** spotlight === full-height left card with inline area chart. */
  spotlight?: boolean;
  /** Area chart for the spotlight card (T1). Year vs scalar value. */
  spotlightChart?: {
    yLabel: string;
    yUnit?: string;
    yMin?: number;
    yMax?: number;
    data: { year: number; value: number }[];
    current: { year: number; value: number };
  };
}

export interface RegimeBarSegment {
  k: string;
  v: string;
  status: Status;
  sub: string;
}

export interface LiaPull {
  k: string;
  v: string;
}

export interface LiaTake {
  label: string;
  timestamp: string;
  paragraphs: string[];
  pulls: [LiaPull, LiaPull, LiaPull, LiaPull];
}

export interface DepMapNode {
  id: string;
  tcode: "T1" | "T2" | "T3" | "T4" | "T5";
  name: string;
  status: Status;
  statusLabel: string;
  position: "left-top" | "left-mid" | "left-bot" | "center" | "right";
}

export interface DepMapEdge {
  from: string;
  to: string;
  label: string;
  variant: "solid" | "dashed" | "accent";
}

export interface CascadeStep {
  badge: string;
  title: string;
  body: string;
  target?: boolean;
}

export interface ConsolidatedTrigger {
  status: Status;
  name: string;
  source: string;
  desc: string;
  fromTabs: string;
}

export interface SummaryData {
  hero: {
    eyebrow: string;
    eyebrowStrong?: string;
    headline: string;
    headlineAccent: string;
    lede: string;
    stats: { k: string; v: string; status: Status }[];
  };
  liaTake: LiaTake;
  regimeBar: {
    label: string;
    subLabel: string;
    segments: RegimeBarSegment[];
  };
  frameworkStatus: {
    label: string;
    subLabel: string;
    cards: FrameworkStatusCard[];
  };
  depMap: {
    label: string;
    subLabel: string;
    sub: string;
    nodes: DepMapNode[];
    edges: DepMapEdge[];
  };
  cascade: {
    label: string;
    subLabel: string;
    sub: string;
    row1: CascadeStep[];
    row2: CascadeStep[];
  };
  watchlist: {
    label: string;
    subLabel: string;
    triggers: ConsolidatedTrigger[];
  };
  sources: string;
}
