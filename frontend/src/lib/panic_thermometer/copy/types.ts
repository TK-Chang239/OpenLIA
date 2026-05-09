/**
 * Typed fallback copy contracts for the Panic Thermometer dashboard.
 * Backend's untyped resolved_values/extras shape is intentionally bypassed —
 * the viewer renders from these types until panel runners emit a strict
 * superset of the shapes below.
 */

export type Severity = "calm" | "elevated" | "high" | "severe" | "crisis";
export type PanelStatus = "green" | "amber" | "red" | "darkred";
export type PanelId = "oil" | "inflation" | "fed" | "wage" | "diplomacy";
export type Tone = "dovish" | "neutral" | "hawkish" | "crisis";

export interface SummaryStats {
  composite: Severity;
  scoreOutOf5: number;
  redCount: number;
  totalPanels: number;
  delta7day: number;
  lastRefreshIso: string;
  lastRefreshLabel: string;
  trend: "widening" | "narrowing" | "flat";
  asOfDateLabel: string;
}

export interface SeverityScaleEntry {
  severity: Severity;
  label: string;
  detail: string;
  reachedOn: string | null;
  isCurrent?: boolean;
}

export interface HeroCopy {
  eyebrowTime: string;
  headline: string;
  accent: string;
  ledeFragments: Array<
    | { kind: "text"; value: string }
    | { kind: "strong"; value: string }
    | { kind: "hot"; value: string }
    | { kind: "warm"; value: string }
  >;
  thermBulbFillPct: number;
  scale: SeverityScaleEntry[];
}

export interface ScorecardEntry {
  panelId: PanelId;
  index: string;
  title: string;
  status: PanelStatus;
  stampLabel: string;
  primaryValue: string;
  primaryUnit?: string;
  miniChart: {
    kind: "spark-area" | "stripe-bars" | "bars" | "progress";
    points?: number[];
    bars?: Array<{ value: number; status: PanelStatus }>;
    stripes?: Array<{ status: PanelStatus | "neutral"; intensity?: number }>;
    progressPct?: number;
    threshold?: number;
  };
  detail: Array<
    | { kind: "text"; value: string }
    | { kind: "strong"; value: string; tone?: "bad" | "warn" | "ok" | "neutral" }
  >;
}

export interface RuleRow {
  status: PanelStatus;
  formulaParts: Array<
    | { kind: "var"; value: string }
    | { kind: "op"; value: string }
    | { kind: "lit"; value: string; gloss?: string }
    | { kind: "text"; value: string }
  >;
  check: string;
  matched: boolean;
}

export interface ParamRow {
  key: string;
  value: string;
}

export interface PanelChrome {
  panelId: PanelId;
  num: string;
  title: string;
  subtitle: string;
  pillTone: "bad" | "warn" | "ok" | "darkred";
  pillLabel: string;
  lastUpdate: string;
  rules: RuleRow[];
  params: ParamRow[];
  presetLabel: string;
}

export interface OilPanel extends PanelChrome {
  panelId: "oil";
  bigValue: string;
  bigValueTone: "bad" | "warn" | "ok";
  bigValueUnit: string;
  bigValueStamp: { tone: "bad" | "warn" | "ok"; label: string };
  narrative: PanelLine;
  chart: {
    yLabels: string[];
    xLabels: string[];
    thresholdPrice: number;
    yMin: number;
    yMax: number;
    streakStartIndex: number;
    streakStartLabel: string;
    series: number[];
    currentLabel: string;
  };
  streak: {
    days: number;
    targetDays: number;
    segments: Array<{ status: "amber" | "red" | "darkred"; widthPct: number; leftPct: number }>;
    markerPct: number;
    foots: Array<{ days: string; tone: "neutral" | "bad"; label: string }>;
  };
}

export interface InflationPanel extends PanelChrome {
  panelId: "inflation";
  bigValue: string;
  bigValueTone: "warn" | "bad";
  bigValueUnit: string;
  bigValueStamp: { tone: "warn" | "bad"; label: string };
  narrative: PanelLine;
  chart: {
    bands: Array<{ tone: "amber" | "red" | "dark"; yPct: [number, number] }>;
    thresholds: Array<{ tone: "amber" | "red" | "dark"; level: number; label: string }>;
    yLabels: string[];
    xLabels: string[];
    yMin: number;
    yMax: number;
    tipSeries: number[];
    michiganDots: Array<{ x: number; y: number; isCurrent?: boolean; label?: string }>;
    tipCurrentLabel: string;
  };
}

export interface FedPanel extends PanelChrome {
  panelId: "fed";
  bigQuote: string;
  narrative: PanelLine;
  postureTimeline: Array<{
    label: string;
    tone: Tone;
    isCurrent?: boolean;
  }>;
  headlines: Array<{
    when: string;
    time: string;
    body: HeadlineFragment[];
    source: string;
  }>;
  keywords: Record<Tone, { matches: string[]; standard: string[] }>;
  meta: { newsLookbackDays: number; daysSinceFomc: number };
}

export interface WagePanel extends PanelChrome {
  panelId: "wage";
  bigValue: string;
  bigValueUnit: string;
  bigValueStamp: { tone: "bad" | "darkred"; label: string };
  narrative: PanelLine;
  bars: Array<{ month: string; value: number; status: PanelStatus; isCurrent?: boolean }>;
  thresholds: { amber: number; red: number };
  yMax: number;
  consecutiveBracket: { startIndex: number; endIndex: number; label: string };
}

export interface DiplomacyPanel extends PanelChrome {
  panelId: "diplomacy";
  countdown: {
    elapsed: number;
    total: number;
    remaining: number;
    progressPct: number;
    startLabel: string;
    endLabel: string;
  };
  signals: { progress: number; escalation: number };
  headlines: Array<{
    when: string;
    time: string;
    body: HeadlineFragment[];
    source: string;
  }>;
}

export type AnyPanel = OilPanel | InflationPanel | FedPanel | WagePanel | DiplomacyPanel;

export interface PanelLine {
  parts: Array<
    | { kind: "text"; value: string }
    | { kind: "strong"; value: string; tone?: "bad" | "warn" | "ok" }
  >;
}

export type HeadlineFragment =
  | { kind: "text"; value: string }
  | { kind: "mark"; value: string; tone: Tone };

export interface ReleaseRow {
  whenDay: string;
  whenTime: string;
  name: string;
  source: string;
  actual: string;
  actualTone: "pos" | "neg" | "warn" | "neutral";
  consensus: string;
  prior: string;
  surprise: string;
  surpriseTone: "pos" | "neg" | "warn" | "neutral";
  surpriseTag?: string;
}

export interface VerdictCopy {
  metaParts: string[];
  headline: string;
  paragraphs: VerdictParagraph[];
  tags: Array<{ label: string; href: string }>;
  generatedAt: string;
  confidence: number;
}

export interface VerdictParagraph {
  parts: Array<
    | { kind: "text"; value: string }
    | { kind: "strong"; value: string; tone?: "bad" | "warn" | "ok" }
  >;
}
