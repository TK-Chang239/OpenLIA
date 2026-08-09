/**
 * Adapters that turn the live `/dashboard` payload into the strongly-typed
 * view-model shapes the Panic Thermometer components consume.
 *
 * Rules of the road:
 * - No fabricated numbers. Every number rendered here is read from the payload
 *   or computed from payload numbers + params. Static labels/units/titles are
 *   constants.
 * - Prose (narrative sentences, pills, stamps, headlines) is generated from the
 *   real numbers.
 * - Fields with no backend source are filled with empty/neutral defaults
 *   (e.g. `rules: []`, `xLabels: []`, `reachedOn: null`).
 */

import type {
  DashboardPayload,
  PanelId as ApiPanelId,
  PanelResult,
  PanelStatus as ApiPanelStatus,
} from "../../api/panic-thermometer";
import type {
  DiplomacyPanel,
  FedPanel,
  HeroCopy,
  InflationPanel,
  OilPanel,
  PanelStatus,
  ParamRow,
  ScorecardEntry,
  Severity,
  SummaryStats,
  Tone,
  VerdictCopy,
  WagePanel,
} from "./copy/types";

// --------------------------------------------------------------------------
// Small helpers
// --------------------------------------------------------------------------

/** Map the API panel status onto the tighter copy status union. */
export function mapStatus(s: ApiPanelStatus): PanelStatus {
  switch (s) {
    case "green":
      return "green";
    case "amber":
      return "amber";
    case "red":
      return "red";
    case "dark_red":
      return "darkred";
    case "disabled":
      // No dedicated copy status; render as a calm/green swatch with an "Off"
      // label supplied by the caller.
      return "green";
  }
}

/** Chrome pill tone derived from the copy status. */
export function statusToPillTone(
  s: PanelStatus,
): "bad" | "warn" | "ok" | "darkred" {
  switch (s) {
    case "green":
      return "ok";
    case "amber":
      return "warn";
    case "red":
      return "bad";
    case "darkred":
      return "darkred";
  }
}

const STATUS_LABEL: Record<PanelStatus, string> = {
  green: "Green",
  amber: "Amber",
  red: "Red",
  darkred: "Dark red",
};

function statusLabel(api: ApiPanelStatus): string {
  return api === "disabled" ? "Off" : STATUS_LABEL[mapStatus(api)];
}

const SEVERITY_LABEL: Record<Severity, string> = {
  calm: "Calm",
  elevated: "Elevated",
  high: "High",
  severe: "Severe",
  crisis: "Crisis",
};

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function bool(v: unknown): boolean {
  return v === true;
}

function str(v: unknown): string {
  return typeof v === "string" ? v : "";
}

function strArray(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x): x is string => typeof x === "string") : [];
}

function fmt(n: number, digits = 1): string {
  return n.toFixed(digits);
}

/** Build ParamRow[] from a payload params record (stable insertion order). */
function paramRows(params: Record<string, unknown>): ParamRow[] {
  return Object.entries(params).map(([key, value]) => ({
    key,
    value: formatParamValue(value),
  }));
}

function formatParamValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return String(value);
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/** Nice-round chart bounds with padding around a real series. */
function seriesBounds(series: number[]): { yMin: number; yMax: number } {
  if (series.length === 0) return { yMin: 0, yMax: 1 };
  const lo = Math.min(...series);
  const hi = Math.max(...series);
  if (lo === hi) {
    const pad = Math.abs(lo) * 0.05 || 1;
    return { yMin: lo - pad, yMax: hi + pad };
  }
  const pad = (hi - lo) * 0.15;
  return { yMin: lo - pad, yMax: hi + pad };
}

/** Sample a series down to ~n points for a compact sparkline (0..28 inverted). */
function sparkPoints(series: number[], slots = 13): number[] {
  if (series.length === 0) return [];
  const pick =
    series.length <= slots
      ? series
      : Array.from({ length: slots }, (_, i) =>
          series[Math.round((i / (slots - 1)) * (series.length - 1))],
        );
  const lo = Math.min(...pick);
  const hi = Math.max(...pick);
  const range = hi - lo || 1;
  // SVG y grows downward; map high value -> small y (top), low value -> 28.
  return pick.map((v) => 26 - ((v - lo) / range) * 24);
}

export function panelStatus(p: DashboardPayload, id: ApiPanelId): ApiPanelStatus {
  return p.panels[id]?.status ?? "disabled";
}

// --------------------------------------------------------------------------
// Summary + hero
// --------------------------------------------------------------------------

export function adaptSummaryStats(p: DashboardPayload): SummaryStats {
  const level = p.composite.level as Severity;
  const score = num(p.composite.score);
  const red = num(p.composite.red_count);
  const total = 5;
  const iso = p.generated_at || new Date().toISOString();
  const trend: SummaryStats["trend"] =
    red >= 3 ? "widening" : red === 0 ? "flat" : "narrowing";
  return {
    composite: level,
    scoreOutOf5: score,
    redCount: red,
    totalPanels: total,
    // No historical snapshot is available in the payload; 7-day delta is not
    // computable, so it is reported as flat (0).
    delta7day: 0,
    lastRefreshIso: iso,
    lastRefreshLabel: formatTimeLabel(iso),
    trend,
    asOfDateLabel: `Live · ${formatDateLabel(iso)}`,
  };
}

function formatTimeLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function formatDateLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d
    .toLocaleDateString(undefined, {
      weekday: "short",
      day: "2-digit",
      month: "short",
      year: "numeric",
    })
    .toUpperCase();
}

/** Compact "07 Aug" date for chips/labels; empty string when unparseable. */
function shortDate(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short" });
}

/** Compact "HH:MM" time for chips/labels; empty string when unparseable. */
function shortTime(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

const SEVERITY_ORDER: Severity[] = [
  "calm",
  "elevated",
  "high",
  "severe",
  "crisis",
];

const SEVERITY_DETAIL: Record<Severity, string> = {
  calm: "0 red",
  elevated: "1 red",
  high: "2 red",
  severe: "3+ red",
  crisis: "4+ red",
};

export function adaptHero(p: DashboardPayload): HeroCopy {
  const level = p.composite.level as Severity;
  const score = num(p.composite.score);
  const red = num(p.composite.red_count);
  const fillPct = Math.max(0, Math.min(100, (score / 5) * 100));

  const scale = SEVERITY_ORDER.map((severity) => ({
    severity,
    label: SEVERITY_LABEL[severity],
    detail: SEVERITY_DETAIL[severity],
    // No historical "reached on" timestamp is available in the payload.
    reachedOn: severity === level ? "▶ today" : null,
    isCurrent: severity === level,
  }));

  // Which panels are currently red / dark-red drives the accent sentence.
  const hotPanels = describeHotPanels(p);
  const accent =
    hotPanels.length > 0
      ? `${hotPanels.join(", ")} driving the reading.`
      : "No panels are on a red reading.";

  return {
    eyebrowTime: `Panic Thermometer · ${formatTimeLabel(p.generated_at)}`,
    headline: `${red} of 5 panels red.`,
    accent,
    ledeFragments: buildHeroLede(p, level, score, red),
    thermBulbFillPct: fillPct,
    scale,
  };
}

/** Human names for the panels that are red / dark-red. */
function describeHotPanels(p: DashboardPayload): string[] {
  const names: Partial<Record<ApiPanelId, string>> = {
    oil: "Oil duration",
    inflation: "Inflation expectations",
    fed_language: "Fed posture",
    wage_growth: "Wage growth",
    diplomacy: "Diplomacy window",
  };
  const hot: string[] = [];
  (Object.keys(names) as ApiPanelId[]).forEach((id) => {
    const st = panelStatus(p, id);
    if (st === "red" || st === "dark_red") hot.push(names[id] as string);
  });
  return hot;
}

function buildHeroLede(
  p: DashboardPayload,
  level: Severity,
  score: number,
  red: number,
): HeroCopy["ledeFragments"] {
  const frags: HeroCopy["ledeFragments"] = [
    { kind: "text", value: "Composite reads " },
    { kind: "strong", value: SEVERITY_LABEL[level] },
    { kind: "text", value: ` at ${fmt(score)} / 5.0 with ` },
    { kind: red >= 3 ? "hot" : "warm", value: `${red} of 5 panels red` },
    { kind: "text", value: "." },
  ];

  const oil = p.panels.oil;
  if (oil) {
    const streak = num(oil.resolved_values.streak_days);
    if (streak > 0) {
      frags.push(
        { kind: "text", value: " Oil has held above threshold for " },
        { kind: "hot", value: `${streak} sessions` },
        { kind: "text", value: "." },
      );
    }
  }
  const wage = p.panels.wage_growth;
  if (wage) {
    const val = num(wage.extras.value);
    if (val !== 0) {
      frags.push(
        { kind: "text", value: " Latest AHE printed " },
        { kind: "hot", value: `${val > 0 ? "+" : ""}${fmt(val, 1)}% MoM` },
        { kind: "text", value: "." },
      );
    }
  }
  const dip = p.panels.diplomacy;
  if (dip) {
    const remaining = num(dip.extras.days_remaining);
    frags.push({
      kind: "text",
      value: ` Diplomacy window has ${remaining} days remaining.`,
    });
  }
  return frags;
}

// --------------------------------------------------------------------------
// Scorecards
// --------------------------------------------------------------------------

export function adaptScorecards(p: DashboardPayload): ScorecardEntry[] {
  return [
    scorecardOil(p.panels.oil),
    scorecardInflation(p.panels.inflation),
    scorecardFed(p.panels.fed_language),
    scorecardWage(p.panels.wage_growth),
    scorecardDiplomacy(p.panels.diplomacy),
  ];
}

function scorecardOil(r: PanelResult): ScorecardEntry {
  const status = mapStatus(r.status);
  const streak = num(r.resolved_values.streak_days);
  const price = num(r.resolved_values.price);
  const threshold = num(r.params.price_threshold);
  const priceSeries = r.raw_series.price ?? [];
  return {
    panelId: "oil",
    index: "D1 · OIL",
    title: "Oil price duration",
    status,
    stampLabel: statusLabel(r.status),
    primaryValue: String(streak),
    primaryUnit: "d",
    miniChart:
      priceSeries.length > 0
        ? { kind: "spark-area", points: sparkPoints(priceSeries) }
        : { kind: "spark-area", points: [] },
    detail: [
      { kind: "text", value: "Price " },
      { kind: "strong", value: `$${fmt(price, 2)}`, tone: status === "green" ? "ok" : "bad" },
      { kind: "text", value: " vs " },
      { kind: "strong", value: `$${fmt(threshold, 2)}`, tone: "neutral" },
      { kind: "text", value: " threshold" },
    ],
  };
}

function scorecardInflation(r: PanelResult): ScorecardEntry {
  const status = mapStatus(r.status);
  const mich = num(r.extras.michigan_5y);
  const amber = num(r.params.level_amber);
  const tipSeries = r.raw_series.tip_price ?? [];
  return {
    panelId: "inflation",
    index: "D2 · INFL",
    title: "Inflation expectations",
    status,
    stampLabel: statusLabel(r.status),
    primaryValue: fmt(mich, 1),
    primaryUnit: "%",
    miniChart:
      tipSeries.length > 0
        ? { kind: "spark-area", points: sparkPoints(tipSeries) }
        : { kind: "spark-area", points: [] },
    detail: [
      { kind: "text", value: "Michigan 5y " },
      { kind: "strong", value: `${fmt(mich, 1)}%`, tone: status === "green" ? "ok" : "warn" },
      { kind: "text", value: " vs " },
      { kind: "strong", value: `${fmt(amber, 1)}%` },
      { kind: "text", value: " amber line" },
    ],
  };
}

const TONE_LABEL: Record<Tone, string> = {
  dovish: "Dovish",
  neutral: "Neutral",
  hawkish: "Hawkish",
  crisis: "Crisis",
};

function fedTone(r: PanelResult): Tone {
  if (bool(r.extras.crisis_keyword_detected)) return "crisis";
  if (bool(r.extras.hawkish_keyword_detected)) return "hawkish";
  if (bool(r.extras.dovish_keyword_detected)) return "dovish";
  return "neutral";
}

function scorecardFed(r: PanelResult): ScorecardEntry {
  const status = mapStatus(r.status);
  const tone = fedTone(r);
  const phrase = str(r.extras.matched_phrase);
  const days = num(r.extras.days_since_fomc);
  return {
    panelId: "fed",
    index: "D3 · FED",
    title: "Fed language tracker",
    status,
    stampLabel: statusLabel(r.status),
    primaryValue: TONE_LABEL[tone],
    miniChart: {
      kind: "stripe-bars",
      stripes: (["dovish", "neutral", "hawkish", "crisis"] as Tone[]).map((tn) => ({
        status:
          tn === "dovish"
            ? "green"
            : tn === "neutral"
              ? "neutral"
              : tn === "hawkish"
                ? "red"
                : "darkred",
        intensity: tn === tone ? 1 : 0.3,
      })),
    },
    detail: [
      { kind: "text", value: phrase ? `Matched ` : "No trigger phrase" },
      ...(phrase
        ? [
            {
              kind: "strong" as const,
              value: `"${phrase}"`,
              tone: (tone === "hawkish" || tone === "crisis" ? "bad" : "ok") as
                | "bad"
                | "ok",
            },
          ]
        : []),
      { kind: "text", value: ` · ${days}d post-FOMC` },
    ],
  };
}

function scorecardWage(r: PanelResult): ScorecardEntry {
  const status = mapStatus(r.status);
  const value = num(r.extras.value);
  const consec = num(r.extras.consecutive_count);
  const series = (r.raw_series.value ?? []).slice(-12);
  const amber = num(r.params.wage_threshold_amber);
  const red = num(r.params.wage_threshold_red);
  return {
    panelId: "wage",
    index: "D4 · WAGE",
    title: "Wage growth (AHE)",
    status,
    stampLabel: statusLabel(r.status),
    primaryValue: `${value > 0 ? "+" : ""}${fmt(value, 1)}`,
    primaryUnit: "% MoM",
    miniChart:
      series.length > 0
        ? {
            kind: "bars",
            bars: barHeights(series).map((h, i) => ({
              value: h,
              status: wageBarStatus(series[i], amber, red),
            })),
          }
        : { kind: "bars", bars: [] },
    detail: [
      { kind: "text", value: `${consec} consecutive over ` },
      { kind: "strong", value: `${fmt(amber, 1)}%`, tone: status === "green" ? "ok" : "bad" },
      { kind: "text", value: " threshold" },
    ],
  };
}

function scorecardDiplomacy(r: PanelResult): ScorecardEntry {
  const status = mapStatus(r.status);
  const elapsed = num(r.extras.days_elapsed);
  const remaining = num(r.extras.days_remaining);
  const total = num(r.params.window_days, elapsed + remaining);
  const pct = total > 0 ? Math.max(0, Math.min(100, (elapsed / total) * 100)) : 0;
  return {
    panelId: "diplomacy",
    index: "D5 · DIPL",
    title: "Diplomatic progress",
    status,
    stampLabel: statusLabel(r.status),
    primaryValue: String(remaining),
    primaryUnit: "d left",
    miniChart: { kind: "progress", progressPct: pct },
    detail: [
      { kind: "text", value: `Day ${elapsed} of ${total} · ` },
      {
        kind: "strong",
        value: bool(r.extras.escalation_detected) ? "escalation" : "no escalation",
        tone: bool(r.extras.escalation_detected) ? "bad" : "ok",
      },
    ],
  };
}

/** Scale a small MoM-style series into 0..24 bar heights for the mini chart. */
function barHeights(series: number[]): number[] {
  const hi = Math.max(...series, 0.0001);
  return series.map((v) => Math.max(2, (Math.max(0, v) / hi) * 24));
}

function wageBarStatus(v: number, amber: number, red: number): PanelStatus {
  if (v >= red) return "red";
  if (v >= amber) return "amber";
  return "green";
}

// --------------------------------------------------------------------------
// Deep-dive panels
// --------------------------------------------------------------------------

const PRESET_LABEL = "Preset · Report defaults";

export function adaptOil(r: PanelResult): OilPanel {
  const status = mapStatus(r.status);
  const pillTone = statusToPillTone(status);
  const streak = num(r.resolved_values.streak_days);
  const price = num(r.resolved_values.price);
  const threshold = num(r.params.price_threshold);
  const streakAmber = num(r.params.streak_amber, 1);
  const streakRed = num(r.params.streak_red, 30);
  const streakDarkRed = num(r.params.streak_dark_red, 90);

  const series = r.raw_series.price ?? [];
  const bounds = seriesBounds([...series, threshold]);
  const bigTone: "bad" | "warn" | "ok" =
    status === "green" ? "ok" : status === "amber" ? "warn" : "bad";

  // Streak progression bar: 0 -> amber -> red -> dark-red target.
  const target = streakDarkRed;
  const amberEnd = (streakAmber / target) * 100;
  const redEnd = (streakRed / target) * 100;
  const markerPct = Math.max(0, Math.min(100, (streak / target) * 100));

  return {
    panelId: "oil",
    num: "D1",
    title: "Oil price duration",
    subtitle: "How long the tracked contract has held above the threshold",
    pillTone,
    pillLabel: `${statusLabel(r.status)} · ${streak}d streak`,
    lastUpdate: `${str(r.params.ticker) || "—"}`,
    presetLabel: PRESET_LABEL,
    rules: [],
    params: paramRows(r.params),
    bigValue: `$${fmt(price, 2)}`,
    bigValueTone: bigTone,
    bigValueUnit: `${str(r.params.ticker) || "price"} · latest close`,
    bigValueStamp: {
      tone: bigTone,
      label: price >= threshold ? `Above $${fmt(threshold, 2)}` : `Below $${fmt(threshold, 2)}`,
    },
    narrative: {
      parts: [
        { kind: "text", value: "Held above the " },
        { kind: "strong", value: `$${fmt(threshold, 2)}`, tone: "bad" },
        { kind: "text", value: " threshold for " },
        {
          kind: "strong",
          value: `${streak} consecutive sessions`,
          tone: bigTone === "ok" ? "ok" : "bad",
        },
        {
          kind: "text",
          value: ` — red triggers at ${streakRed}, the extended-duration mark at ${streakDarkRed}.`,
        },
      ],
    },
    chart: {
      yLabels: axisLabels(bounds.yMin, bounds.yMax, (v) => `$${v.toFixed(0)}`),
      xLabels: [],
      thresholdPrice: threshold,
      yMin: bounds.yMin,
      yMax: bounds.yMax,
      streakStartIndex: streakStartIndex(series, threshold),
      streakStartLabel: "streak start",
      series,
      currentLabel: `$${fmt(price || (series[series.length - 1] ?? 0), 2)} · latest`,
    },
    streak: {
      days: streak,
      targetDays: target,
      segments: [
        { status: "amber", widthPct: Math.max(0, redEnd - amberEnd), leftPct: amberEnd },
        { status: "red", widthPct: Math.max(0, 100 - redEnd), leftPct: redEnd },
        { status: "darkred", widthPct: 0, leftPct: 100 },
      ],
      markerPct,
      foots: [
        { days: `${streakAmber}d`, tone: "neutral", label: "amber" },
        { days: `${streakRed}d`, tone: "bad", label: "red" },
        { days: `${streakDarkRed}d`, tone: "neutral", label: "extended" },
      ],
    },
  };
}

function streakStartIndex(series: number[], threshold: number): number {
  // Walk back from the end while the series stays above threshold.
  if (series.length === 0) return 0;
  let i = series.length - 1;
  while (i > 0 && series[i] >= threshold) i -= 1;
  return i;
}

export function adaptInflation(r: PanelResult): InflationPanel {
  const status = mapStatus(r.status);
  const pillTone = statusToPillTone(status);
  const mich = num(r.extras.michigan_5y);
  const michPrev = num(r.extras.michigan_prev);
  const missing = bool(r.extras.michigan_5y_missing);
  const amber = num(r.params.level_amber, 2.5);
  const red = num(r.params.level_red, 3.0);
  const dark = num(r.params.level_dark_red, 3.5);
  const tipLatest = num(r.extras.tip_price_latest);

  const tipSeries = r.raw_series.tip_price ?? [];
  const yMin = Math.min(amber - 0.5, mich - 0.3, 2.0);
  const yMax = Math.max(dark + 0.2, mich + 0.3);
  const range = yMax - yMin || 1;
  const bigTone: "warn" | "bad" = status === "darkred" || status === "red" ? "bad" : "warn";
  const delta = mich - michPrev;

  // Bands (top->bottom in yPct where 0% is top of plot = yMax):
  const yPctFor = (level: number) =>
    Math.max(0, Math.min(100, ((yMax - level) / range) * 100));

  return {
    panelId: "inflation",
    num: "D2",
    title: "Inflation expectations",
    subtitle: "Michigan 5y survey · TIP price confirmation",
    pillTone,
    pillLabel: `${statusLabel(r.status)}${missing ? " · survey pending" : ""}`,
    lastUpdate: missing ? "Survey pending" : "Michigan 5y",
    presetLabel: PRESET_LABEL,
    rules: [],
    params: paramRows(r.params),
    bigValue: `${fmt(mich, 1)}%`,
    bigValueTone: bigTone,
    bigValueUnit: "Michigan 5y · y/y",
    bigValueStamp: {
      tone: bigTone,
      label: `${delta >= 0 ? "+" : ""}${fmt(delta, 1)}pp m/m`,
    },
    narrative: {
      parts: [
        { kind: "text", value: "Michigan 5y at " },
        { kind: "strong", value: `${fmt(mich, 1)}%`, tone: bigTone },
        {
          kind: "text",
          value: ` — ${mich >= red ? "above" : mich >= amber ? "above the amber, below the" : "below the"} ${fmt(red, 1)}% red line. `,
        },
        { kind: "text", value: "Amber at " },
        { kind: "strong", value: `${fmt(amber, 1)}%` },
        { kind: "text", value: ", extended-risk at " },
        { kind: "strong", value: `${fmt(dark, 1)}%` },
        { kind: "text", value: "." },
      ],
    },
    chart: {
      bands: [
        { tone: "amber", yPct: [yPctFor(red), yPctFor(amber)] },
        { tone: "red", yPct: [yPctFor(dark), yPctFor(red)] },
        { tone: "dark", yPct: [0, yPctFor(dark)] },
      ],
      thresholds: [
        { tone: "dark", level: dark, label: `${fmt(dark, 1)}% — extended` },
        { tone: "red", level: red, label: `${fmt(red, 1)}% — red` },
        { tone: "amber", level: amber, label: `${fmt(amber, 1)}% — amber` },
      ],
      yLabels: axisLabels(yMin, yMax, (v) => v.toFixed(1)),
      xLabels: [],
      yMin,
      yMax,
      tipSeries,
      michiganDots: buildMichiganDots(mich),
      tipCurrentLabel: tipLatest ? `TIP $${fmt(tipLatest, 2)}` : "",
    },
  };
}

/**
 * We only have a single Michigan reading (no monthly history), so the chart
 * shows one current dot placed on the plot at its real level.
 */
function buildMichiganDots(mich: number): InflationPanel["chart"]["michiganDots"] {
  return [{ x: 630, y: mich, isCurrent: true, label: `${fmt(mich, 1)}%` }];
}

export function adaptFed(r: PanelResult): FedPanel {
  const status = mapStatus(r.status);
  const pillTone = statusToPillTone(status);
  const tone = fedTone(r);
  const phrase = str(r.extras.matched_phrase);
  const headline = str(r.extras.matched_headline);
  const matchedDate = str(r.extras.matched_date);
  const daysSinceFomc = num(r.extras.days_since_fomc);
  const lookback = num(r.params.news_lookback_days);

  const dovish = strArray(r.params.dovish_keywords);
  const neutral = strArray(r.params.neutral_keywords);
  const hawkish = strArray(r.params.hawkish_keywords);
  const crisis = strArray(r.params.crisis_keywords);
  const matchList = phrase ? [phrase] : [];
  const matchedDateLabel = shortDate(matchedDate);

  return {
    panelId: "fed",
    num: "D3",
    title: "Fed language tracker",
    subtitle: "Posture detection from FOMC + Fed newsflow",
    pillTone,
    pillLabel: `${statusLabel(r.status)} · ${TONE_LABEL[tone].toLowerCase()}`,
    lastUpdate: matchedDateLabel ? `Matched ${matchedDateLabel}` : `${daysSinceFomc}d post-FOMC`,
    presetLabel: PRESET_LABEL,
    rules: [],
    params: paramRows(r.params),
    bigQuote: phrase ? `"${phrase}"` : `${TONE_LABEL[tone]} posture`,
    narrative: {
      parts: [
        { kind: "text", value: "Detected " },
        {
          kind: "strong",
          value: TONE_LABEL[tone].toLowerCase(),
          tone: tone === "hawkish" || tone === "crisis" ? "bad" : tone === "dovish" ? "ok" : undefined,
        },
        { kind: "text", value: phrase ? ` posture on the phrase ` : " posture in recent Fed newsflow." },
        ...(phrase
          ? [
              {
                kind: "strong" as const,
                value: `"${phrase}"`,
                tone: (tone === "hawkish" || tone === "crisis" ? "bad" : "ok") as "bad" | "ok",
              },
              { kind: "text" as const, value: "." },
            ]
          : []),
      ],
    },
    postureTimeline: [
      {
        label: matchedDateLabel || "current",
        tone,
        isCurrent: true,
      },
    ],
    headlines:
      headline || matchedDate
        ? [
            {
              when: matchedDateLabel,
              time: shortTime(matchedDate),
              source: "Fed newsflow",
              body: [
                ...(headline ? [{ kind: "text" as const, value: headline }] : []),
                ...(phrase
                  ? [{ kind: "mark" as const, value: phrase, tone }]
                  : []),
              ],
            },
          ]
        : [],
    keywords: {
      dovish: { matches: tone === "dovish" ? matchList : [], standard: dovish },
      neutral: { matches: tone === "neutral" ? matchList : [], standard: neutral },
      hawkish: { matches: tone === "hawkish" ? matchList : [], standard: hawkish },
      crisis: { matches: tone === "crisis" ? matchList : [], standard: crisis },
    },
    meta: { newsLookbackDays: lookback, daysSinceFomc },
  };
}

export function adaptWage(r: PanelResult): WagePanel {
  const status = mapStatus(r.status);
  const pillTone = statusToPillTone(status);
  const value = num(r.extras.value);
  const prev = num(r.extras.prev_value);
  const consec = num(r.extras.consecutive_count);
  const avg12 = num(r.extras.avg_12m);
  const amber = num(r.params.wage_threshold_amber, 0.4);
  const red = num(r.params.wage_threshold_red, 0.5);
  const required = num(r.params.consecutive_required, 2);

  const series = (r.raw_series.value ?? []).slice(-12);
  const bars = series.map((v, i) => ({
    month: "",
    value: v,
    status: wageBarStatus(v, amber, red),
    isCurrent: i === series.length - 1,
  }));
  const yMax = Math.max(red + 0.2, value + 0.2, ...series.map((v) => v + 0.1), 0.8);
  const bigTone: "bad" | "darkred" = status === "darkred" ? "darkred" : "bad";

  // Highlight the trailing consecutive run above the amber line.
  const startIndex = Math.max(0, series.length - Math.max(1, consec));
  const endIndex = Math.max(startIndex, series.length - 1);

  return {
    panelId: "wage",
    num: "D4",
    title: "Wage growth (Average Hourly Earnings)",
    subtitle: `${required} consecutive months above threshold = spiral risk`,
    pillTone,
    pillLabel: `${statusLabel(r.status)} · ${consec} consecutive`,
    lastUpdate: "AHE MoM",
    presetLabel: PRESET_LABEL,
    rules: [],
    params: paramRows(r.params),
    bigValue: `${value > 0 ? "+" : ""}${fmt(value, 1)}%`,
    bigValueUnit: "AHE · MoM",
    bigValueStamp: {
      tone: bigTone,
      label: consec >= required ? `${consec} consecutive hot prints` : `${consec} above threshold`,
    },
    narrative: {
      parts: [
        { kind: "text", value: "Latest AHE printed " },
        { kind: "strong", value: `${value > 0 ? "+" : ""}${fmt(value, 1)}% MoM`, tone: status === "green" ? "ok" : "bad" },
        {
          kind: "text",
          value: ` — ${consec} of the required ${required} consecutive months above the ${fmt(amber, 1)}% line. `,
        },
        { kind: "text", value: "12-month average " },
        { kind: "strong", value: `${fmt(avg12, 2)}%` },
        { kind: "text", value: `, prior ${fmt(prev, 1)}%.` },
      ],
    },
    bars,
    thresholds: { amber, red },
    yMax,
    consecutiveBracket: {
      startIndex,
      endIndex,
      label: `${consec} consecutive`,
    },
  };
}

export function adaptDiplomacy(r: PanelResult): DiplomacyPanel {
  const status = mapStatus(r.status);
  const pillTone = statusToPillTone(status);
  const elapsed = num(r.extras.days_elapsed);
  const remaining = num(r.extras.days_remaining);
  const total = num(r.params.window_days, elapsed + remaining);
  const progressDetected = bool(r.extras.progress_detected);
  const escalationDetected = bool(r.extras.escalation_detected);
  const progressHeadlines = strArray(r.extras.matched_progress_headlines);
  const escalationHeadlines = strArray(r.extras.matched_escalation_headlines);
  const progressPct = total > 0 ? Math.max(0, Math.min(100, (elapsed / total) * 100)) : 0;

  const headlines = [
    ...progressHeadlines.map((h) => headlineFrom(h, "dovish")),
    ...escalationHeadlines.map((h) => headlineFrom(h, "hawkish")),
  ];

  return {
    panelId: "diplomacy",
    num: "D5",
    title: "Diplomatic progress",
    subtitle: "Rolling milestone window with news support",
    pillTone,
    pillLabel: `${statusLabel(r.status)} · ${elapsed}/${total} days elapsed`,
    lastUpdate: `${remaining}d remaining`,
    presetLabel: PRESET_LABEL,
    rules: [],
    params: paramRows(r.params),
    countdown: {
      elapsed,
      total,
      remaining,
      progressPct,
      startLabel: "Day 0 · window opened",
      endLabel: `Day ${total} · window closes`,
    },
    signals: {
      progress: progressDetected ? progressHeadlines.length || 1 : progressHeadlines.length,
      escalation: escalationDetected ? escalationHeadlines.length || 1 : escalationHeadlines.length,
    },
    headlines,
  };
}

function headlineFrom(
  text: string,
  tone: Tone,
): DiplomacyPanel["headlines"][number] {
  return {
    when: "",
    time: "",
    source: tone === "hawkish" ? "escalation signal" : "progress signal",
    body: [{ kind: "text", value: text }],
  };
}

// --------------------------------------------------------------------------
// Verdict
// --------------------------------------------------------------------------

export function adaptVerdict(p: DashboardPayload): VerdictCopy {
  const level = p.composite.level as Severity;
  const score = num(p.composite.score);
  const red = num(p.composite.red_count);
  const hot = describeHotPanels(p);
  const headline =
    hot.length > 0
      ? `${hot.join(" and ")} ${hot.length === 1 ? "is" : "are"} on a red reading; composite sits at ${SEVERITY_LABEL[level]}.`
      : `No panels are red; composite sits at ${SEVERITY_LABEL[level]}.`;

  return {
    metaParts: [
      "Panic Thermometer",
      `${SEVERITY_LABEL[level]} · ${red}/5 red`,
      `Composite ${fmt(score)}/5.0`,
    ],
    headline,
    paragraphs: [],
    tags: [],
    generatedAt: formatTimeLabel(p.generated_at),
    confidence: 0,
  };
}

// --------------------------------------------------------------------------
// Axis label helper
// --------------------------------------------------------------------------

/** Five evenly spaced axis labels from yMax (top) down to yMin (bottom). */
function axisLabels(
  yMin: number,
  yMax: number,
  format: (v: number) => string,
): string[] {
  const steps = 5;
  return Array.from({ length: steps }, (_, i) => {
    const v = yMax - ((yMax - yMin) * i) / (steps - 1);
    return format(v);
  });
}
