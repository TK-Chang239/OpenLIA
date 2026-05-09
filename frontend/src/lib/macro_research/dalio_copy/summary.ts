/**
 * Summary tab — synthesis surface for the 5 Dalio frameworks.
 *
 * Framework-status cards (T1–T5) are derived from each tab's own fallback
 * (debt_cycle / four_seasons / all_weather / world_order / five_forces).
 * Title, status pill, summary line, mini-visual data and stat tiles all
 * flow from the canonical T fallback, so a change to a per-T verdict
 * propagates to the Summary card without a parallel edit here.
 *
 * Summary-only structural data (regime bar, dep map, cascade narrative,
 * spotlight chart series, consolidated watchlist) is authored here.
 *
 * TODO(backend): replace with `getDashboardSummary()` once the backend
 * produces a payload matching `SummaryData`.
 */
import type {
  AllWeatherData,
  DebtCycleData,
  FiveForcesData,
  FourSeasonsData,
  FrameworkStatusCard,
  Status,
  SummaryData,
  T1Tone,
  T2Tone,
  T3Tone,
  T4Tone,
  T5Tone,
  WorldOrderData,
} from "./types";
import { DEBT_CYCLE_FALLBACK } from "./debt_cycle";
import { FOUR_SEASONS_FALLBACK } from "./four_seasons";
import { ALL_WEATHER_FALLBACK } from "./all_weather";
import { WORLD_ORDER_FALLBACK } from "./world_order";
import { FIVE_FORCES_FALLBACK } from "./five_forces";

type AnyTone = T1Tone | T2Tone | T3Tone | T4Tone | T5Tone;

function toneToStatus(tone: AnyTone): Status {
  switch (tone) {
    case "red":    return "bad";
    case "amber":  return "warn";
    case "green":  return "ok";
    case "blue":   return "info";
    case "purple": return "info";
  }
}

function quadrantIndex(xPct: number, yPct: number): number {
  const right = xPct >= 50;
  const bottom = yPct >= 50;
  if (!right && !bottom) return 0;
  if (right && !bottom) return 1;
  if (!right && bottom) return 2;
  return 3;
}

function deriveT1Card(data: DebtCycleData): FrameworkStatusCard {
  const pill = data.header.pills[0];
  return {
    tcode: "T1",
    slug: "debt_cycle",
    title: "Debt & Money Cycle",
    stamp: { label: pill.label, status: toneToStatus(pill.tone) },
    summary: data.cardSummary,
    verdictLine: data.cardSummary,
    miniVisual: "bars",
    miniData: data.scorecard.rows.map((r) => r.fillPct),
    stats: data.scorecard.rows.slice(0, 3).map((r) => ({
      k: r.name.replace(/\s*\(.*\)/, "").split("/")[0].trim(),
      v: r.current,
      status: toneToStatus(r.currentTone),
    })),
    footLabel: "Open T1 dashboard",
    spotlight: true,
    spotlightChart: {
      yLabel: "Debt / GDP",
      yUnit: "%",
      yMin: 40,
      yMax: 140,
      data: [
        { year: 1999, value: 60.5 },
        { year: 2002, value: 56.8 },
        { year: 2005, value: 60.2 },
        { year: 2008, value: 67.7 },
        { year: 2011, value: 95.5 },
        { year: 2013, value: 100.7 },
        { year: 2015, value: 100.6 },
        { year: 2017, value: 103.2 },
        { year: 2020, value: 126.4 },
        { year: 2022, value: 119.8 },
        { year: 2024, value: 122.3 },
        { year: 2026, value: 125.2 },
      ],
      current: { year: 2026, value: 125.2 },
    },
  };
}

function deriveT2Card(data: FourSeasonsData): FrameworkStatusCard {
  const pill = data.header.pills[0];
  const now = data.quadrant.markers.find((m) => m.variant === "now") ?? data.quadrant.markers[0];
  const rows = data.scorecard.rows;
  const pmi = rows.find((r) => /pmi/i.test(r.name));
  const gdp = rows.find((r) => /gdp/i.test(r.name));
  const cpi = rows.find((r) => /^cpi/i.test(r.name) || /cpi.*all/i.test(r.name));
  return {
    tcode: "T2",
    slug: "four_seasons",
    acid: true,
    title: "Four Seasons",
    stamp: { label: pill.label, status: toneToStatus(pill.tone) },
    summary: data.cardSummary,
    miniVisual: "quadrant",
    miniData: { active: true, index: quadrantIndex(now.xPct, now.yPct) },
    stats: [
      pmi ? { k: "PMI", v: pmi.current, status: toneToStatus(pmi.currentTone) } : null,
      gdp ? { k: "GDP Q1", v: gdp.current, status: toneToStatus(gdp.currentTone) } : null,
      cpi ? { k: "CPI y/y", v: cpi.current, status: toneToStatus(cpi.currentTone) } : null,
    ].filter((s): s is { k: string; v: string; status: Status } => s !== null),
    footLabel: "Open T2 dashboard",
  };
}

function deriveT3Card(data: AllWeatherData): FrameworkStatusCard {
  const pill = data.header.pills[0];
  const ref = data.comparison.reference.slices;
  const bench = data.comparison.benchmark.slices;
  const stocksRef = ref.find((s) => /stock|equit/i.test(s.label));
  const stocksBench = bench.find((s) => /stock|equit/i.test(s.label));
  const goldRef = ref.find((s) => /gold/i.test(s.label));
  const goldBench = bench.find((s) => /gold/i.test(s.label));
  const bondsRef = ref.find((s) => /bond|treas/i.test(s.label));
  const bondsBench = bench.find((s) => /bond|treas/i.test(s.label));
  function delta(refV?: number, benchV?: number): { v: string; status: Status } {
    if (refV === undefined || benchV === undefined) return { v: "—", status: "flat" };
    const diff = refV - benchV;
    const sign = diff >= 0 ? "+" : "";
    const status: Status = Math.abs(diff) < 0.5 ? "flat" : diff > 0 ? "ok" : "bad";
    return { v: `${sign}${diff.toFixed(1)}pp`, status };
  }
  return {
    tcode: "T3",
    slug: "all_weather",
    title: "All-Weather",
    stamp: { label: pill.label, status: toneToStatus(pill.tone) },
    summary: data.cardSummary,
    miniVisual: "ring",
    miniData: data.comparison.reference.slices.map((s) => s.pct),
    stats: [
      { k: "Stocks", ...delta(stocksRef?.pct, stocksBench?.pct) },
      { k: "Bonds", ...delta(bondsRef?.pct, bondsBench?.pct) },
      { k: "Gold", ...delta(goldRef?.pct, goldBench?.pct) },
    ],
    footLabel: "Open T3 dashboard",
  };
}

function deriveT4Card(data: WorldOrderData): FrameworkStatusCard {
  const pill = data.header.pills[0];
  const activeIdx = data.empireCycle.stages.findIndex((s) => s.state === "active");
  const rows = data.scorecard.rows;
  const usd = rows.find((r) => /usd|reserve/i.test(r.name));
  const gold = rows.find((r) => /gold|cb/i.test(r.name));
  const treas = rows.find((r) => /treasur|holding/i.test(r.name));
  return {
    tcode: "T4",
    slug: "world_order",
    title: "World Order",
    stamp: { label: pill.label, status: toneToStatus(pill.tone) },
    summary: data.cardSummary,
    miniVisual: "stage",
    miniData: { active: activeIdx >= 0, index: activeIdx >= 0 ? activeIdx : 4 },
    stats: [
      usd ? { k: "USD reserve", v: usd.current, status: toneToStatus(usd.currentTone) } : { k: "USD", v: "—", status: "flat" as Status },
      gold ? { k: "CB gold", v: gold.current, status: toneToStatus(gold.currentTone) } : { k: "CB gold", v: "—", status: "flat" as Status },
      treas ? { k: "UST held", v: treas.current, status: toneToStatus(treas.currentTone) } : { k: "UST", v: "—", status: "flat" as Status },
    ],
    footLabel: "Open T4 dashboard",
  };
}

function deriveT5Card(data: FiveForcesData): FrameworkStatusCard {
  const badge = data.header.badges[0];
  const rows = data.scorecard.rows;
  const critical = rows.filter((r) => r.scorePct >= 70).length;
  const aggregate = rows.length > 0 ? rows.reduce((s, r) => s + r.scorePct, 0) / rows.length / 10 : 0;
  return {
    tcode: "T5",
    slug: "five_forces",
    title: "Five Forces",
    stamp: { label: badge.label, status: toneToStatus(badge.tone) },
    summary: data.cardSummary,
    miniVisual: "forces",
    miniData: data.scorecard.rows.map((r) => r.scorePct),
    stats: [
      { k: "Aggregate", v: aggregate.toFixed(1), status: aggregate >= 7 ? "bad" : aggregate >= 5 ? "warn" : "ok" },
      { k: "Critical", v: String(critical), status: critical >= 3 ? "bad" : critical >= 1 ? "warn" : "ok" },
      { k: "Forces", v: `${rows.length} / 5`, status: "info" },
    ],
    footLabel: "Open T5 dashboard",
  };
}

const FRAMEWORK_CARDS: FrameworkStatusCard[] = [
  deriveT1Card(DEBT_CYCLE_FALLBACK),
  deriveT2Card(FOUR_SEASONS_FALLBACK),
  deriveT3Card(ALL_WEATHER_FALLBACK),
  deriveT4Card(WORLD_ORDER_FALLBACK),
  deriveT5Card(FIVE_FORCES_FALLBACK),
];

/* ─── Regime bar — derive at-a-glance segments from each T's first pill ─── */

function deriveRegimeSegment(
  k: string,
  pill: { label: string; tone: AnyTone },
  sub: string,
): { k: string; v: string; status: Status; sub: string } {
  return { k, v: pill.label, status: toneToStatus(pill.tone), sub };
}

const REGIME_SEGMENTS = [
  deriveRegimeSegment(
    "T1 · Debt Cycle",
    DEBT_CYCLE_FALLBACK.header.pills[0],
    `${DEBT_CYCLE_FALLBACK.scorecard.rows.filter((r) => r.statusTone === "red").length} / ${DEBT_CYCLE_FALLBACK.scorecard.rows.length} indicators in warn`,
  ),
  deriveRegimeSegment(
    "T2 · Season",
    FOUR_SEASONS_FALLBACK.header.pills[0],
    "Growth slowing · CPI re-accelerating",
  ),
  deriveRegimeSegment(
    "T4 · World Order",
    WORLD_ORDER_FALLBACK.header.pills[0],
    "USD reserve −6.4pp / 10Y",
  ),
  deriveRegimeSegment(
    "T5 · Forces",
    { label: FIVE_FORCES_FALLBACK.header.badges[0].label, tone: FIVE_FORCES_FALLBACK.header.badges[0].tone },
    "Last 3-of-5 simultaneity: 1937–42",
  ),
];

/* ─── Consolidated watchlist — 6 highest-priority triggers across all T's ─── */

function pickTrigger(
  tabs: string,
  source: string,
  status: Status,
  name: string,
  desc: string,
): { status: Status; name: string; source: string; desc: string; fromTabs: string } {
  return { status, name, source, desc, fromTabs: tabs };
}

const CONSOLIDATED_TRIGGERS = [
  pickTrigger(
    "From T2 · T3",
    "ICE BAML · daily",
    "bad",
    "HY OAS widens through 3.5%",
    "The single biggest credit-side confirmation of T2's autumn call. Currently 2.90%. Re-rates T3 gold to 15% (one of three triggers).",
  ),
  pickTrigger(
    "From T1",
    "JEC + BEA",
    "bad",
    "Interest rate exceeds GDP growth",
    "CRFB FY2031 baseline · debt-spiral threshold. If hit early due to re-inflation or recession, T1 phase reclassifies from late plateau to early deleveraging.",
  ),
  pickTrigger(
    "From T4 · T5",
    "IMF COFER · qtr",
    "bad",
    "USD reserve share < 55%",
    "Currently 56.9%. A clean break of 55% is the structural threshold below which reserve currency status is widely perceived as eroding.",
  ),
  pickTrigger(
    "From T1 · T3",
    "DFII10 · monthly",
    "warn",
    "TIPS real yield falls below +1%",
    "Currently +1.94%. A further 0.5–1pp decline materially strengthens the gold thesis and is the second of three T3 re-rate triggers.",
  ),
  pickTrigger(
    "From T2",
    "BEA · monthly",
    "warn",
    "Core PCE prints > 2.7% × 2 months",
    "A two-month run above 2.7% removes the disinflation narrative and locks in T2's autumn read. Pulls Fed cut path to none.",
  ),
  pickTrigger(
    "From T2 · T3",
    "BEA + ISM",
    "ok",
    "Core PCE < 2% × 2 months and ISM > 52",
    "The clean rejection signal. Reverts T3 to the strategic 30/40/15/7.5/7.5 weights. Walks back the autumn call toward late summer.",
  ),
];

export const SUMMARY_FALLBACK: SummaryData = {
  hero: {
    eyebrow: "Macro · April 2026 · ",
    eyebrowStrong: "3 of 5 forces critical · regime: late-plateau / autumn",
    headline: "Three forces critical, simultaneously.",
    headlineAccent: "Late plateau, tipping into autumn.",
    lede:
      "All five Dalio frameworks point in the same direction. T1 reads late plateau (3 indicators in warn). T2 is transitioning summer → autumn. T4 shows accelerating reserve-currency erosion. T5 aggregates 3-of-5 forces critical — the cleanest historical analog is 1937–42. T3 turns this into a tactical autumn tilt: cut long bonds, double commodities, lift gold. The five frameworks are coherent — that is the signal.",
    stats: [
      { k: "Active forces", v: "3 / 5", status: "bad" },
      { k: "Aggregate", v: "8.3 / 10", status: "bad" },
      { k: "Tactical alpha", v: "+5.5pp", status: "ok" },
      { k: "Conviction", v: "71 / 100", status: "info" },
      { k: "Last refresh", v: "Apr 14 · 14:22 ET", status: "flat" },
    ],
  },
  liaTake: {
    label: "LIA's cross-framework take",
    timestamp: "Apr 14 · 14:22 ET",
    paragraphs: [
      "Five frameworks. One read. The unusual property of this snapshot is **coherence** — all five are pointing in mutually-reinforcing directions, which is rare. Dalio's empirical claim is that 3-of-5 forces simultaneously critical narrows the response set: **F1 (debt) constrains F2 (internal conflict); F3 (tech) feeds F2; F2 feeds F4 (external)** via tariff and sanction policy.",
      "The clean expression is the gold thesis cascade — T1 says monetary headroom is limited, T2 says we're in autumn, T4 says CBs are buying gold at >1,000 t/yr, so T5 confluence reads as an environment where **real assets dominate**, and T3 implements that with a +2.5pp gold tilt.",
      "The risk is that T2's autumn read is conviction-62 — credit (HY OAS at 2.9%) hasn't confirmed yet. *Watch HY OAS through 3.5%* as the single biggest re-rating signal.",
    ],
    pulls: [
      { k: "Action", v: "Adopt T3 tactical tilt" },
      { k: "Window", v: "Quarterly review" },
      { k: "Top trigger", v: "HY OAS ≥ 3.5%" },
      { k: "Top rejection", v: "Core PCE < 2% × 2m" },
    ],
  },
  regimeBar: {
    label: "Regime · at-a-glance",
    subLabel: "Today's verdict per framework",
    segments: REGIME_SEGMENTS,
  },
  frameworkStatus: {
    label: "Frameworks · drill-in",
    subLabel: "5 cards · click for full detail",
    cards: FRAMEWORK_CARDS,
  },
  depMap: {
    label: "Cross-framework dependency map",
    subLabel: "How signals flow between T1–T5",
    sub:
      "Each framework consumes upstream readings and emits a verdict downstream. T5 is the aggregator (consumes T1, T2, T4); T3 is the implementer (consumes T1, T2, T4, T5). Solid arrows are direct numeric feeds; dashed arrows are conceptual cross-checks.",
    nodes: [
      { id: "t1", tcode: "T1", name: "Debt Cycle", status: "bad", statusLabel: "CRITICAL", position: "left-top" },
      { id: "t2", tcode: "T2", name: "Four Seasons", status: "bad", statusLabel: "AUTUMN", position: "left-mid" },
      { id: "t4", tcode: "T4", name: "World Order", status: "warn", statusLabel: "ELEVATED", position: "left-bot" },
      { id: "t5", tcode: "T5", name: "Five Forces", status: "bad", statusLabel: "3 / 5 CRITICAL", position: "center" },
      { id: "t3", tcode: "T3", name: "All-Weather", status: "ok", statusLabel: "TACTICAL TILT", position: "right" },
    ],
    edges: [
      { from: "t1", to: "t5", label: "F1 input", variant: "solid" },
      { from: "t2", to: "t5", label: "F2/F3 input", variant: "solid" },
      { from: "t4", to: "t5", label: "F4 input", variant: "solid" },
      { from: "t1", to: "t3", label: "gold tilt rationale", variant: "dashed" },
      { from: "t2", to: "t3", label: "season → legs", variant: "solid" },
      { from: "t5", to: "t3", label: "confluence response", variant: "accent" },
    ],
  },
  cascade: {
    label: "Gold thesis · cross-framework cascade",
    subLabel: "How four frameworks compose to one position",
    sub:
      "The gold tilt in T3 is the cleanest expression of cross-framework coherence. Each upstream framework contributes one independent argument; T5 confirms confluence; T3 implements.",
    row1: [
      { badge: "T1 · debt", title: "Real yields trending lower", body: "DFII10 +1.94% · down 0.36pp YoY · monetary headroom limited." },
      { badge: "T2 · season", title: "Autumn quadrant", body: "Median real return for gold in autumn: **+14.1%**. Lead leg." },
      { badge: "T4 · order", title: "CB structural bid", body: "1,000+ tonnes/year · USD reserve −6.4pp / 10Y · sanctions weaponised." },
    ],
    row2: [
      { badge: "T5 · forces", title: "Confluence · 3 / 5 critical", body: "F1 + F4 both flag debasement preconditions. Confluence multiplies." },
      {
        badge: "T3 · IMPLEMENT",
        title: "Gold 7.5% → 10% · re-rate to 15% on triggers",
        body: "+2.5pp now, fund from long bonds. Three triggers raise to 15%: DFII10 <1%, HY OAS ≥3.5%, debt-spiral threshold.",
        target: true,
      },
    ],
  },
  watchlist: {
    label: "Consolidated watchlist · 6 triggers",
    subLabel: "Top signals across T1–T5",
    triggers: CONSOLIDATED_TRIGGERS,
  },
  sources:
    "CEIC / BEA / CBO / PGPF / WGC / IMF COFER / ICE BAML / Bridgewater Associates / Pew Research / BLS / Federal Reserve H.15 / Munich Re / CRFB. Cross-framework readings synthesised from individual T1–T5 dashboards. Disclosure · macro framework exercise produced by OpenLia for institutional research use; not investment advice.",
};
