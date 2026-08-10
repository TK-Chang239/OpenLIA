// Macro Research demo fixtures. Powers the department page's Summary tab and
// all five Dalio-framework dashboards (T1 Debt Cycle, T2 Four Seasons, T3
// All-Weather, T4 World Order, T5 Five Forces).
//
// Shape notes (matched against src/api/macro_research.ts + every framework
// view under src/pages/departments/macro_research/ + the shared widgets under
// src/components/macro_research/):
//  - The page loads the framework list via GET /dashboards, then each view
//    calls getDashboard<T>(slug) -> GET /dashboards/:slug which returns a
//    DashboardResponse<T> = { payload, generated_at, is_stale, provenance }.
//    The payload T is the per-framework interface from
//    src/lib/macro_research/dalio_copy/types.ts (SummaryData, DebtCycleData,
//    FourSeasonsData, AllWeatherData, WorldOrderData, FiveForcesData).
//  - Because every dashboard is authored here with a full payload, the views
//    settle on the populated article immediately; the empty-state "Generate"
//    flow is never reached in the demo. The refresh POST is still wired so a
//    stray click returns a benign queued result (read-only demo).
//  - The header cadence control reads GET /schedule and writes PUT/DELETE
//    /schedule; those return a benign ScheduleState (auto == no cron).
//
// Regime story (consistent across all six payloads): late-cycle US expansion,
// disinflating toward target, the Fed has begun a shallow easing cycle, debt
// service is the binding long-term constraint, the world order is fracturing
// at the margin (de-dollarization, central-bank gold accumulation), and the
// cross-framework confluence is structurally constructive on gold and real
// assets. Illustrative sample data only — not real market data or advice.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, hoursAgo } from "../clock";
import { INVESTOR } from "./persona";

import type {
  DashboardResponse,
  DashboardSummary,
  RunAssessmentResult,
  ScheduleState,
} from "../../api/macro_research";
import type {
  AllWeatherData,
  DebtCycleData,
  FiveForcesData,
  FourSeasonsData,
  SummaryData,
  WorldOrderData,
} from "../../lib/macro_research/dalio_copy/types";

const BASE = "/api/departments/macro_research";

// Freshly assessed: mark the whole set as generated a few hours ago so the
// "live" chrome reads as current against the frozen demo clock.
const GENERATED_AT = hoursAgo(3);

const PROVENANCE = "report_dash_mr · illustrative demo assessment";

// Persona portfolio label — T3 All-Weather references the persona book
// conceptually as the "reference" sleeve versus the classic All-Weather mix.
const PORTFOLIO_LABEL = `${INVESTOR.displayName} book`;

const SOURCES =
  "Illustrative sample data for this OpenLIA demonstration — treasury and " +
  "FRED-style series, IMF COFER-style reserve shares, World Gold Council-style " +
  "central-bank flows, and market quotes are all synthetic. Nothing here is " +
  "real market data or investment advice.";

// ---------------------------------------------------------------------------
// Framework registry (GET /dashboards). Summary is filtered out of the T1-T5
// tab row by the page but is still requested as its own slug.
// ---------------------------------------------------------------------------

const DASHBOARDS: DashboardSummary[] = [
  { slug: "debt_cycle", display_name: "Debt Cycle" },
  { slug: "four_seasons", display_name: "Four Seasons" },
  { slug: "all_weather", display_name: "All-Weather" },
  { slug: "world_order", display_name: "World Order" },
  { slug: "five_forces", display_name: "Five Forces" },
];

// ===========================================================================
// SUMMARY  (SummaryData)
// ===========================================================================

const SUMMARY: SummaryData = {
  hero: {
    eyebrow: "Cross-framework regime read · ",
    eyebrowStrong: "late-cycle, disinflating, easing",
    headline: "Five Dalio lenses point to the same place:",
    headlineAccent: "own real assets, fade duration risk.",
    lede:
      "The US expansion is mature but intact. Inflation is drifting back toward " +
      "target and the Fed has begun a shallow easing cycle, yet the long-term " +
      "debt cycle is the binding constraint — real yields sit above trend growth " +
      "and interest costs are crowding the fiscal path. All five frameworks agree " +
      "on the direction of travel even where they disagree on timing.",
    stats: [
      { k: "Real GDP (SAAR)", v: "1.9%", status: "warn" },
      { k: "Core PCE (YoY)", v: "2.6%", status: "ok" },
      { k: "Fed funds (upper)", v: "4.25%", status: "info" },
      { k: "US 10Y", v: "4.16%", status: "info" },
      { k: "Gold (spot)", v: "$2,940", status: "acid" },
    ],
  },
  liaTake: {
    label: "LIA's cross-framework take",
    timestamp: "Assessed 3h ago",
    paragraphs: [
      "Read the five frameworks together and the signal is unusually clean. " +
        "**Four Seasons** puts us in *disinflationary slowdown* — growth cooling, " +
        "inflation falling — the quadrant that historically favours duration. But " +
        "**Debt Cycle** overrides the naive duration trade: with debt service near " +
        "cycle highs and real yields above trend growth, the long bond carries a " +
        "fiscal-supply tax the season model doesn't price.",
      "**World Order** and **Five Forces** explain why the tension resolves toward " +
        "*real assets rather than bonds*. Reserve managers are diversifying out of " +
        "the dollar at the margin and central banks are accumulating gold at a " +
        "record pace; the internal-conflict and external-conflict forces are both " +
        "elevated. **All-Weather** confirms the persona book is under-hedged to the " +
        "one environment — a fiscal-led inflation restart — that would hurt a " +
        "conventional 60/40 the most.",
      "Net: this is a *late-cycle easing* regime where the confluence trade is a " +
        "structural overweight to gold and real assets, a neutral-to-underweight " +
        "on long duration, and equities held but hedged for a growth wobble.",
    ],
    pulls: [
      { k: "Regime", v: "Late-cycle · disinflating · easing" },
      { k: "Confluence", v: "Gold / real assets overweight" },
      { k: "Fade", v: "Long-duration Treasuries" },
      { k: "Watch", v: "Fiscal-led inflation restart" },
    ],
  },
  regimeBar: {
    label: "At-a-glance regime verdict",
    subLabel: "6 dimensions",
    segments: [
      { k: "Growth", v: "Cooling", status: "warn", sub: "Below-trend, not contracting" },
      { k: "Inflation", v: "Disinflating", status: "ok", sub: "Core PCE 2.6% → target" },
      { k: "Policy", v: "Easing", status: "info", sub: "Fed cut, shallow path" },
      { k: "Liquidity", v: "Neutral", status: "flat", sub: "QT tapering, reserves ample" },
      { k: "Credit", v: "Tight-but-orderly", status: "warn", sub: "IG +92bp, HY +348bp" },
      { k: "Confluence", v: "Own gold", status: "acid", sub: "5/5 frameworks aligned" },
    ],
  },
  frameworkStatus: {
    label: "Framework status board",
    subLabel: "5 dashboards",
    cards: [
      {
        tcode: "T1",
        slug: "debt_cycle",
        title: "Debt Cycle",
        spotlight: true,
        stamp: { label: "Late-cycle constraint", status: "warn" },
        verdictLine:
          "Debt service is the **binding constraint**: real yields sit *above* " +
          "trend growth and interest costs are crowding the fiscal path. The cycle " +
          "is late but not yet at a forced-deleveraging break.",
        summary:
          "Debt service near cycle highs; real yields above trend growth. Late " +
          "long-term debt cycle, not yet at a break.",
        miniVisual: "bars",
        miniData: [58, 61, 66, 72, 79, 84],
        stats: [
          { k: "Debt/GDP", v: "122%", status: "bad" },
          { k: "Real 10Y", v: "1.6%", status: "warn" },
          { k: "Net interest", v: "3.4% GDP", status: "bad" },
        ],
        footLabel: "Open T1 dashboard",
        spotlightChart: {
          yLabel: "Federal net interest",
          yUnit: "% of GDP",
          yMin: 1,
          yMax: 4,
          data: [
            { year: 2015, value: 1.5 },
            { year: 2017, value: 1.6 },
            { year: 2019, value: 1.8 },
            { year: 2021, value: 1.6 },
            { year: 2023, value: 2.5 },
            { year: 2025, value: 3.1 },
          ],
          current: { year: 2026, value: 3.4 },
        },
      },
      {
        tcode: "T2",
        slug: "four_seasons",
        title: "Four Seasons",
        stamp: { label: "Disinflationary slowdown", status: "info" },
        summary:
          "Growth falling, inflation falling — the lower-left quadrant. History " +
          "favours duration here, but the debt cycle overrides.",
        miniVisual: "quadrant",
        miniData: { active: true, index: 2 },
        stats: [
          { k: "Growth", v: "Falling", status: "warn" },
          { k: "Inflation", v: "Falling", status: "ok" },
          { k: "Persist", v: "58%", status: "info" },
        ],
        footLabel: "Open T2 dashboard",
      },
      {
        tcode: "T3",
        slug: "all_weather",
        title: "All-Weather",
        stamp: { label: "Under-hedged to inflation", status: "warn" },
        summary:
          "The persona book is balanced for growth shocks but thin on inflation " +
          "protection — the one box a fiscal-led restart would punish.",
        miniVisual: "ring",
        miniData: [32, 28, 22, 18],
        stats: [
          { k: "Gold", v: "5%", status: "warn" },
          { k: "Duration", v: "Heavy", status: "warn" },
          { k: "Vs A-W", v: "Δ inflation", status: "bad" },
        ],
        footLabel: "Open T3 dashboard",
      },
      {
        tcode: "T4",
        slug: "world_order",
        title: "World Order",
        stamp: { label: "Fracturing at the margin", status: "warn" },
        summary:
          "USD reserve share is drifting lower and central banks are buying gold " +
          "at a record pace. Late-empire markers, not a rupture.",
        miniVisual: "stage",
        miniData: { active: true, index: 4 },
        stats: [
          { k: "USD reserves", v: "57%", status: "warn" },
          { k: "CB gold", v: "+1,040t", status: "acid" },
          { k: "Stage", v: "5 / 6", status: "warn" },
        ],
        footLabel: "Open T4 dashboard",
      },
      {
        tcode: "T5",
        slug: "five_forces",
        acid: true,
        title: "Five Forces",
        stamp: { label: "3 of 5 elevated", status: "bad" },
        summary:
          "Debt, internal conflict and external conflict are all running hot; the " +
          "reinforcement loops are live. Aggregate stress in the amber-red band.",
        miniVisual: "forces",
        miniData: [82, 74, 46, 71, 55],
        stats: [
          { k: "Aggregate", v: "6.6", status: "bad" },
          { k: "Critical", v: "3 / 5", status: "bad" },
          { k: "Contagion", v: "High", status: "bad" },
        ],
        footLabel: "Open T5 dashboard",
      },
    ],
  },
  depMap: {
    label: "Cross-framework dependency map",
    subLabel: "how the lenses feed each other",
    sub:
      "Solid lines are direct numeric feeds; dashed lines are conceptual " +
      "cross-checks; the green line is the confluence response the five " +
      "frameworks converge on.",
    nodes: [
      { id: "t1", tcode: "T1", name: "Debt Cycle", status: "warn", statusLabel: "Late-cycle", position: "left-top" },
      { id: "t2", tcode: "T2", name: "Four Seasons", status: "info", statusLabel: "Disinflation", position: "left-mid" },
      { id: "t4", tcode: "T4", name: "World Order", status: "warn", statusLabel: "Fracturing", position: "left-bot" },
      { id: "t5", tcode: "T5", name: "Five Forces", status: "bad", statusLabel: "Elevated", position: "center" },
      { id: "t3", tcode: "T3", name: "All-Weather", status: "warn", statusLabel: "Under-hedged", position: "right" },
    ],
    edges: [
      { from: "t1", to: "t5", label: "debt-service stress", variant: "solid" },
      { from: "t2", to: "t5", label: "growth/inflation inputs", variant: "solid" },
      { from: "t4", to: "t5", label: "conflict forces", variant: "solid" },
      { from: "t1", to: "t2", label: "duration override", variant: "dashed" },
      { from: "t4", to: "t1", label: "fiscal financing", variant: "dashed" },
      { from: "t5", to: "t3", label: "own real assets", variant: "accent" },
    ],
  },
  cascade: {
    label: "Confluence cascade — the gold thesis",
    subLabel: "5 steps",
    sub:
      "How the five lenses chain into one asset conclusion when they agree. Each " +
      "step is a claim the framework above supplies; the target is where they meet.",
    row1: [
      { badge: "T1", title: "Debt is the constraint", body: "Real yields **above** trend growth; interest costs crowd the fiscal path." },
      { badge: "T2", title: "Season favours duration", body: "Disinflationary slowdown historically rewards bonds — *but see T1*." },
      { badge: "T4", title: "Order is fracturing", body: "Reserve managers diversify out of USD; **gold** is the neutral reserve." },
    ],
    row2: [
      { badge: "T5", title: "Forces reinforce", body: "Debt + internal + external conflict loops are all **live** together." },
      { badge: "T3", title: "Book is under-hedged", body: "60/40 is thin on the inflation-restart box the confluence flags." },
      { badge: "→", title: "Own real assets", body: "Overweight **gold / real assets**, neutral-to-under long duration.", target: true },
    ],
  },
  watchlist: {
    label: "Consolidated watchlist — what would change this read",
    subLabel: "6 triggers",
    triggers: [
      {
        status: "bad",
        name: "Fiscal-led inflation restart",
        source: "T1 · T3",
        desc:
          "Core PCE re-accelerates above 3.2% while deficits stay above 6% of GDP — " +
          "flips the season and punishes the under-hedged book.",
        fromTabs: "T1 · T2 · T3",
      },
      {
        status: "warn",
        name: "Long-end supply indigestion",
        source: "T1 · T4",
        desc:
          "30Y auction tails widen and term premium jumps — the fiscal-financing " +
          "channel from World Order into Debt Cycle turns acute.",
        fromTabs: "T1 · T4",
      },
      {
        status: "warn",
        name: "Credit spread breakout",
        source: "T5",
        desc:
          "HY OAS breaks above 500bp — the debt-service loop transmits to the real " +
          "economy and forces the growth quadrant lower.",
        fromTabs: "T2 · T5",
      },
      {
        status: "info",
        name: "Fed pause / re-hike",
        source: "T1 · T2",
        desc:
          "If the shallow easing path stalls, the disinflation read weakens and the " +
          "duration case loses its only support.",
        fromTabs: "T1 · T2",
      },
      {
        status: "acid",
        name: "Central-bank gold acceleration",
        source: "T4 · T5",
        desc:
          "Official-sector buying above 1,200t annualised confirms the reserve " +
          "diversification thesis and the confluence trade.",
        fromTabs: "T4 · T5",
      },
      {
        status: "ok",
        name: "Soft-landing confirmation",
        source: "T2",
        desc:
          "Growth stabilises above trend with inflation still falling — the benign " +
          "case that would soften the whole defensive tilt.",
        fromTabs: "T2 · T3",
      },
    ],
  },
  sources: SOURCES,
};

// ===========================================================================
// T1 — DEBT CYCLE  (DebtCycleData)
// ===========================================================================

const DEBT_CYCLE: DebtCycleData = {
  header: {
    title: "The Long-Term Debt Cycle",
    subtitle: "T1 · Where the US sits on Dalio's big debt cycle",
    pills: [
      { tone: "amber", label: "Late cycle" },
      { tone: "red", label: "Debt service near highs" },
      { tone: "blue", label: "Policy easing" },
    ],
  },
  cardSummary:
    "The US is late in the long-term debt cycle: total debt-to-GDP near record, " +
    "real yields above trend growth, and net interest crowding the fiscal path. " +
    "Not yet a forced deleveraging — but the constraint is now binding.",
  scorecard: {
    rows: [
      {
        name: "Total debt / GDP",
        sub: "Public + private, all sectors",
        current: "122%",
        currentTone: "red",
        currentMeta: "federal debt held by public",
        threshold: "> 100% of GDP",
        status: "Breached",
        statusTone: "red",
        fillPct: 88,
        fillTone: "red",
      },
      {
        name: "Net interest outlay",
        sub: "Federal, % of GDP",
        current: "3.4%",
        currentTone: "red",
        currentMeta: "up from 1.6% in 2021",
        threshold: "> 3% of GDP",
        status: "Breached",
        statusTone: "red",
        fillPct: 85,
        fillTone: "red",
      },
      {
        name: "Real 10Y yield",
        sub: "10Y less trend growth",
        current: "+1.6%",
        currentTone: "amber",
        currentMeta: "10Y 4.16% vs ~2.5% growth",
        threshold: "> trend real growth",
        status: "Above growth",
        statusTone: "amber",
        fillPct: 72,
        fillTone: "amber",
      },
      {
        name: "Debt-service ratio",
        sub: "Private non-financial, BIS-style",
        current: "14.8%",
        currentTone: "amber",
        currentMeta: "income share to debt service",
        threshold: "> 15% (Dalio warn)",
        status: "Approaching",
        statusTone: "amber",
        fillPct: 68,
        fillTone: "amber",
      },
      {
        name: "Primary deficit",
        sub: "Ex-interest, % of GDP",
        current: "-3.9%",
        currentTone: "amber",
        currentMeta: "structural, not cyclical",
        threshold: "sustained deficit ex-interest",
        status: "Persistent",
        statusTone: "amber",
        fillPct: 64,
        fillTone: "amber",
      },
      {
        name: "Central-bank balance sheet",
        sub: "Fed assets, % of GDP",
        current: "23%",
        currentTone: "blue",
        currentMeta: "QT tapering, still elevated",
        threshold: "monetisation capacity",
        status: "Ample space",
        statusTone: "green",
        fillPct: 41,
        fillTone: "green",
      },
    ],
  },
  phaseBox: {
    title: "Phase read — late long-term debt cycle, pre-deleveraging",
    body:
      "The US is in the late stage of the long-term debt cycle. Debt-to-GDP is near " +
      "record and real yields sit above trend growth, so debt service compounds " +
      "faster than the economy — the classic squeeze. What separates 'late' from a " +
      "'break' is that the central bank still owns the reserve currency and has " +
      "balance-sheet space to monetise if forced. That is the release valve, and " +
      "it is precisely why the endgame skews toward currency debasement over " +
      "outright default — bullish real assets, bearish long-duration purchasing power.",
    tone: "amber",
  },
  analogPair: {
    analog: {
      title: "Closest analog — late 1940s, not 2008",
      body:
        "The best parallel is the post-WWII debt overhang, not the 2008 credit " +
        "bust. Debt sits at the sovereign, not the household, level; the resolution " +
        "path is financial repression and slow real erosion, not a private-credit " +
        "cascade. That argues for a grind, not a crash.",
    },
    timeToConstraint: {
      title: "Time-to-constraint — 2 to 4 years",
      body:
        "On current trajectory, net interest crosses defence spending and the " +
        "primary deficit stays structural, the binding fiscal constraint arrives in " +
        "roughly two-to-four years absent policy change. That is the window in which " +
        "the monetisation valve gets tested.",
    },
  },
  policySpace: {
    cards: [
      {
        label: "Rate-cut room",
        value: "425",
        valueTone: "green",
        unit: "bp to zero",
        note: "Ample conventional easing capacity; the Fed has started using it.",
      },
      {
        label: "Balance-sheet room",
        value: "Large",
        valueTone: "blue",
        unit: "QT tapering",
        note: "Assets ~23% of GDP; room to re-expand if long-end supply seizes.",
      },
      {
        label: "Fiscal room",
        value: "Thin",
        valueTone: "red",
        unit: "deficit-financed",
        note: "Interest costs already crowding; little space for new stimulus.",
      },
    ],
  },
  assetThesis: {
    gold: {
      title: "Gold / real assets — structural overweight",
      body:
        "When the resolution path is repression and debasement rather than default, " +
        "the store-of-value bid moves to assets outside the liability structure. " +
        "Gold, real assets and inflation-linked exposure are the natural hedge — and " +
        "the one the confluence of all five frameworks keeps pointing to.",
    },
    longBond: {
      title: "Long-duration Treasuries — fade the rally",
      body:
        "The season model wants duration here, but the debt cycle taxes it: " +
        "persistent supply, a fatter term premium, and a monetisation endgame that " +
        "erodes real value. Own the front end for the cuts; be neutral-to-under the " +
        "long bond.",
    },
  },
  watchlist: {
    rows: [
      {
        tone: "red",
        name: "Net interest > defence spending",
        body:
          "The symbolic fiscal tipping point — once interest outlays exceed defence, " +
          "the political room to run deficits narrows sharply.",
      },
      {
        tone: "amber",
        name: "30Y auction tails widen",
        body:
          "Rising tails and a jumping term premium signal the market is demanding " +
          "more to absorb supply — the constraint turning acute.",
      },
      {
        tone: "amber",
        name: "Debt-service ratio > 15%",
        body:
          "The private-sector Dalio warn line; a breach means income is being " +
          "diverted from spending to servicing debt.",
      },
      {
        tone: "blue",
        name: "Fed restarts balance-sheet expansion",
        body:
          "The monetisation valve opening — confirms the debasement path and is the " +
          "single most bullish real-asset trigger.",
      },
    ],
  },
  verdict: {
    title: "Late-cycle, constraint binding — position for repression, not default",
    body:
      "The US long-term debt cycle is late and the debt-service constraint is now " +
      "binding, but the reserve-currency release valve keeps a forced deleveraging " +
      "off the table for now. The rational stance is to own real assets and the " +
      "front end, fade long duration, and watch the fiscal tipping points that " +
      "would force the monetisation valve open.",
    tone: "amber",
  },
  sources: SOURCES,
};

// ===========================================================================
// T2 — FOUR SEASONS  (FourSeasonsData)
// ===========================================================================

const FOUR_SEASONS: FourSeasonsData = {
  header: {
    title: "The Four Economic Seasons",
    subtitle: "T2 · Growth × inflation regime placement",
    pills: [
      { tone: "blue", label: "Disinflationary slowdown" },
      { tone: "amber", label: "Growth cooling" },
      { tone: "green", label: "Inflation falling" },
    ],
  },
  cardSummary:
    "Growth is decelerating and inflation is falling — the lower-left " +
    "'disinflationary slowdown' quadrant. Historically the season that rewards " +
    "duration and quality, though the debt cycle qualifies the bond call.",
  scorecard: {
    rows: [
      {
        name: "Real GDP (SAAR)",
        sub: "Growth axis · current quarter",
        fillPct: 44,
        fillTone: "amber",
        current: "1.9%",
        currentTone: "amber",
        currentMeta: "below ~2.5% trend",
        trend: "2.8% → 2.3% → 1.9%",
        axisLabel: "Below trend",
        axisTone: "amber",
        direction: "down",
        directionLabel: "Decelerating",
        directionTone: "amber",
      },
      {
        name: "ISM Manufacturing PMI",
        sub: "Growth axis · leading",
        fillPct: 40,
        fillTone: "amber",
        current: "48.6",
        currentTone: "amber",
        currentMeta: "< 50 = contraction",
        trend: "50.1 → 49.2 → 48.6",
        axisLabel: "Contracting",
        axisTone: "amber",
        direction: "down",
        directionLabel: "Softening",
        directionTone: "amber",
      },
      {
        name: "Core PCE (YoY)",
        sub: "Inflation axis · Fed target metric",
        fillPct: 52,
        fillTone: "green",
        current: "2.6%",
        currentTone: "green",
        currentMeta: "toward 2% target",
        trend: "3.2% → 2.9% → 2.6%",
        axisLabel: "Disinflating",
        axisTone: "green",
        direction: "down",
        directionLabel: "Falling",
        directionTone: "green",
      },
      {
        name: "5y5y inflation swap",
        sub: "Inflation axis · expectations",
        fillPct: 55,
        fillTone: "green",
        current: "2.4%",
        currentTone: "green",
        currentMeta: "well-anchored",
        trend: "2.6% → 2.5% → 2.4%",
        axisLabel: "Anchored",
        axisTone: "green",
        direction: "flat",
        directionLabel: "Stable",
        directionTone: "green",
      },
      {
        name: "Payrolls (3m avg)",
        sub: "Growth axis · confirming",
        fillPct: 46,
        fillTone: "amber",
        current: "+118k",
        currentTone: "amber",
        currentMeta: "cooling from +180k",
        trend: "+165k → +142k → +118k",
        axisLabel: "Slowing",
        axisTone: "amber",
        direction: "down",
        directionLabel: "Cooling",
        directionTone: "amber",
      },
    ],
  },
  quadrant: {
    seasons: {
      tl: { name: "Stagflation", sub: "Growth ↓ · Inflation ↑", pillLabel: "Own commodities", tone: "red" },
      tr: { name: "Overheating", sub: "Growth ↑ · Inflation ↑", pillLabel: "Own real assets", tone: "amber" },
      bl: { name: "Disinflationary slowdown", sub: "Growth ↓ · Inflation ↓", pillLabel: "Own duration & quality", tone: "blue" },
      br: { name: "Goldilocks", sub: "Growth ↑ · Inflation ↓", pillLabel: "Own equities", tone: "green" },
    },
    markers: [
      { label: "Now", xPct: 38, yPct: 66, variant: "now", tone: "blue" },
      { label: "1Q ago", xPct: 52, yPct: 44, variant: "prev", tone: "amber" },
    ],
  },
  verdict: {
    title: "Disinflationary slowdown — the duration season, qualified",
    body:
      "Both axes point down: growth is cooling below trend while inflation drifts " +
      "back toward target. That is the season that historically favours duration " +
      "and quality over cyclicals and commodities. The one caveat — from T1 — is " +
      "that the debt cycle taxes the long bond, so the season's duration call is " +
      "expressed at the front end rather than the very long end.",
    sideCards: [
      { label: "Current season", value: "Disinflation", valueTone: "blue", note: "Lower-left quadrant" },
      { label: "Season strength", value: "Moderate", valueTone: "amber", note: "Not deep; near the axis" },
      { label: "Preferred assets", value: "Duration + quality", valueTone: "green", note: "Front-end tilt (see T1)" },
    ],
  },
  parallels: {
    cards: [
      {
        title: "1995 soft landing",
        body:
          "The benign template: the Fed engineered a mid-cycle slowdown, cut " +
          "modestly, and the expansion extended. If growth stabilises here without " +
          "an inflation restart, this is the path.",
      },
      {
        title: "2007 late-cycle rollover",
        body:
          "The cautionary template: a disinflationary slowdown that tipped into " +
          "contraction as credit seized. The T5 credit-spread trigger is the tell " +
          "that separates 1995 from 2007.",
      },
    ],
  },
  transitionRisk: {
    intro:
      "Seasons are sticky but not permanent. From disinflationary slowdown, the " +
      "market usually persists or drifts to Goldilocks; the adverse branch is a " +
      "slide into contraction if credit tightens or a snap back to overheating if " +
      "fiscal impulse reignites inflation.",
    bull: {
      title: "Drift to Goldilocks",
      body:
        "Growth stabilises above trend while inflation keeps falling. Equities " +
        "broaden, cyclicals re-lead, and the defensive tilt can be trimmed.",
    },
    bear: {
      title: "Slide to contraction",
      body:
        "Credit spreads break out and the labour market cracks, pulling growth " +
        "sharply negative while disinflation turns into outright disinflationary " +
        "recession — the season deepens and duration finally works.",
    },
    keyIndicator: {
      title: "Key indicator — HY credit spreads (T5 linkage)",
      body:
        "High-yield OAS is the cleanest single tell for which branch wins. Holding " +
        "below 400bp keeps the soft-landing path alive; a break above 500bp tips " +
        "the season toward contraction.",
    },
    probabilities: {
      currentSeason: "Disinflationary slowdown",
      nextQuarter: [
        { season: "Disinflationary slowdown", prob: 0.58 },
        { season: "Goldilocks", prob: 0.24 },
        { season: "Stagflation", prob: 0.06 },
        { season: "Overheating", prob: 0.12 },
      ],
      persistence: 0.58,
      mostLikelyNext: "Goldilocks (24%)",
      adverseSeason: "Stagflation",
      adverseProb: 0.06,
      expectedDwellQuarters: 2.4,
      horizonQuarters: 4,
      horizon: [
        { season: "Disinflationary slowdown", prob: 0.34 },
        { season: "Goldilocks", prob: 0.38 },
        { season: "Stagflation", prob: 0.11 },
        { season: "Overheating", prob: 0.17 },
      ],
    },
  },
  assetPlaybook: {
    cards: [
      { tone: "green", label: "Duration (front)", posture: "Overweight", body: "2-5y captures the cuts without the long-end fiscal tax." },
      { tone: "blue", label: "Quality equity", posture: "Hold", body: "Cash-generative, low-leverage names outperform in slowdowns." },
      { tone: "amber", label: "Cyclicals", posture: "Underweight", body: "Growth-sensitive; wait for a Goldilocks confirmation." },
      { tone: "purple", label: "Gold", posture: "Overweight", body: "The cross-framework confluence trade (see T1/T4/T5)." },
    ],
  },
  notes: [
    {
      title: "Why the duration call is qualified",
      body:
        "In a textbook disinflationary slowdown you buy the long bond. Here the T1 " +
        "debt cycle overrides at the long end — persistent supply and a monetisation " +
        "endgame — so the season's duration preference is expressed 2-5y.",
    },
    {
      title: "Position vs one quarter ago",
      body:
        "A quarter ago the reading sat closer to overheating (upper-right); the " +
        "marker has migrated down-and-left as both growth and inflation rolled over, " +
        "confirming the season shift rather than a one-print wobble.",
    },
  ],
  sources: SOURCES,
};

// ===========================================================================
// T3 — ALL-WEATHER  (AllWeatherData)
// ===========================================================================

const ALL_WEATHER: AllWeatherData = {
  header: {
    title: "All-Weather Portfolio Audit",
    subtitle: `T3 · ${PORTFOLIO_LABEL} vs the balanced-risk template`,
    pills: [
      { tone: "amber", label: "Under-hedged to inflation" },
      { tone: "green", label: "Balanced to growth shocks" },
      { tone: "blue", label: "Duration-heavy" },
    ],
  },
  cardSummary:
    `Audited against the classic All-Weather template, the ${PORTFOLIO_LABEL} is ` +
    "well balanced for growth shocks but thin on inflation protection — exactly " +
    "the environment the cross-framework read (T1/T2) flags as the tail risk.",
  comparison: {
    label: "Section A — allocation vs the balanced-risk template",
    benchmark: {
      title: "Classic All-Weather (risk-balanced)",
      slices: [
        { label: "Long Treasuries", pct: 40, tone: "accent" },
        { label: "Equities", pct: 30, tone: "olive" },
        { label: "Intermediate bonds", pct: 15, tone: "neutral" },
        { label: "Gold", pct: 7.5, tone: "amber" },
        { label: "Commodities", pct: 7.5, tone: "rust" },
      ],
    },
    reference: {
      title: `${PORTFOLIO_LABEL} (current)`,
      slices: [
        { label: "Equities", pct: 62, tone: "olive" },
        { label: "Bonds (mixed)", pct: 26, tone: "accent" },
        { label: "Gold", pct: 5, tone: "amber" },
        { label: "Cash", pct: 7, tone: "neutral" },
      ],
    },
  },
  coverage: {
    label: "Section B — environment coverage",
    cells: [
      {
        title: "Rising growth",
        badgeLabel: "Covered",
        badgeTone: "green",
        bodyTone: "green",
        body: "Heavy equity weight captures rising-growth environments well.",
        bridgeLabel: "Season link",
        bridge: "Goldilocks / overheating (T2 upper-right).",
      },
      {
        title: "Falling growth",
        badgeLabel: "Covered",
        badgeTone: "green",
        bodyTone: "green",
        body: "Bond sleeve and cash cushion a growth shock adequately.",
        bridgeLabel: "Season link",
        bridge: "Disinflationary slowdown (T2 lower-left) — current.",
      },
      {
        title: "Rising inflation",
        badgeLabel: "Gap",
        badgeTone: "red",
        bodyTone: "red",
        body: "Only 5% gold and no commodities — thin cover for an inflation restart.",
        bridgeLabel: "Risk link",
        bridge: "Fiscal-led restart (T1 debasement path).",
      },
      {
        title: "Falling inflation",
        badgeLabel: "Covered",
        badgeTone: "green",
        bodyTone: "green",
        body: "Duration benefits directly as inflation and yields fall.",
        bridgeLabel: "Season link",
        bridge: "Current disinflation season (T2).",
      },
    ],
  },
  riskParity: {
    label: "Section C — risk contribution, not dollar weight",
    intro:
      "All-Weather balances risk, not capital. Measured by risk contribution, the " +
      `${PORTFOLIO_LABEL} is dominated by equity beta, while the template spreads ` +
      "risk far more evenly across environments.",
    benchmarkTitle: "Classic All-Weather — risk contribution",
    benchmarkBars: [
      { label: "Growth risk", pct: 34 },
      { label: "Rate risk", pct: 30 },
      { label: "Inflation risk", pct: 22 },
      { label: "Credit / other", pct: 14 },
    ],
    referenceTitle: `${PORTFOLIO_LABEL} — risk contribution`,
    referenceBars: [
      { label: "Growth (equity beta)", pct: 71 },
      { label: "Rate risk", pct: 18 },
      { label: "Inflation risk", pct: 6 },
      { label: "Credit / other", pct: 5 },
    ],
    mechanism: {
      title: "Why risk-balance beats dollar-balance",
      body:
        "Equities are far more volatile than bonds, so a 60/40 book that looks " +
        "diversified in dollars is ~90% equity risk. All-Weather sizes each sleeve " +
        "by its volatility so no single environment dominates the outcome.",
    },
  },
  stressTest: {
    label: "Section D — scenario stress test",
    intro:
      `Forward-looking stress of the ${PORTFOLIO_LABEL} versus the balanced-risk ` +
      "template across the four Dalio environments. The inflation-restart row is " +
      "where the current book is most exposed.",
    distribution: {
      title: "12-month return distribution (median vs template)",
      bars: [
        { label: "Base case", userPct: 0.062, refPct: 0.055 },
        { label: "Growth shock", userPct: -0.145, refPct: -0.072 },
        { label: "Inflation restart", userPct: -0.118, refPct: -0.031 },
        { label: "Soft landing", userPct: 0.094, refPct: 0.068 },
      ],
    },
    scenarios: [
      { name: "Base case (current season)", userMedianPct: 0.062, userP5Pct: -0.092, refMedianPct: 0.055, refP5Pct: -0.061, tone: "green" },
      { name: "Growth shock / recession", userMedianPct: -0.145, userP5Pct: -0.268, refMedianPct: -0.072, refP5Pct: -0.141, tone: "amber" },
      { name: "Fiscal-led inflation restart", userMedianPct: -0.118, userP5Pct: -0.231, refMedianPct: -0.031, refP5Pct: -0.098, tone: "red" },
      { name: "Soft landing", userMedianPct: 0.094, userP5Pct: -0.038, refMedianPct: 0.068, refP5Pct: -0.024, tone: "green" },
    ],
    note:
      "The book beats the template in the base and soft-landing cases (more equity " +
      "beta) but loses badly in the inflation-restart tail — the box the confluence " +
      "read flags. Adding gold / real assets narrows that tail.",
  },
  gold: {
    label: "Section E — the gold check",
    title: "Is the book carrying enough gold?",
    needles: [
      { label: "Current 5%", leftPct: 22, tone: "amber" },
      { label: "Template 7.5%", leftPct: 45, tone: "green" },
      { label: "Confluence target ~12%", leftPct: 72, tone: "blue" },
    ],
    stats: [
      { label: "Current weight", value: "5.0%", valueTone: "amber", note: "Below the template's 7.5%." },
      { label: "Template weight", value: "7.5%", valueTone: "green", note: "Classic All-Weather gold sleeve." },
      { label: "Confluence target", value: "~12%", valueTone: "blue", note: "Where T1/T4/T5 jointly point." },
    ],
    rationale: {
      title: "Why lean above the template here",
      body:
        "The cross-framework confluence — a binding debt cycle (T1), a fracturing " +
        "world order (T4), and elevated conflict forces (T5) — argues for a gold " +
        "weight above the static template, not below it. The book's 5% is the single " +
        "clearest gap this audit surfaces.",
    },
  },
  caveats: {
    label: "Section F — caveats",
    cards: [
      {
        title: "All-Weather is regime-agnostic by design",
        body:
          "The template deliberately does not tilt to a forecast. Overlaying the " +
          "confluence view (more gold, front-end duration) is a discretionary " +
          "deviation, not a flaw in the framework.",
      },
      {
        title: "Stress figures are illustrative",
        body:
          "The scenario distributions are synthetic sample outputs for this demo, " +
          "not a calibrated risk model. Treat the direction, not the decimals, as " +
          "the signal.",
      },
    ],
  },
  verdict: {
    title: "Balanced to growth, exposed to inflation — close the gold gap",
    body:
      `The ${PORTFOLIO_LABEL} is well hedged for the current disinflationary ` +
      "slowdown and for growth shocks, but it is thin exactly where the " +
      "cross-framework read says the tail risk lives: a fiscal-led inflation " +
      "restart. The highest-conviction adjustment is lifting the gold / real-asset " +
      "sleeve toward the confluence target and shifting duration to the front end.",
  },
  sources: SOURCES,
};

// ===========================================================================
// T4 — WORLD ORDER  (WorldOrderData)
// ===========================================================================

const WORLD_ORDER: WorldOrderData = {
  header: {
    title: "The Changing World Order",
    subtitle: "T4 · Reserve status, the empire cycle, and wealth shifts",
    pills: [
      { tone: "amber", label: "Late-empire markers" },
      { tone: "red", label: "De-dollarization at the margin" },
      { tone: "green", label: "Record CB gold buying" },
    ],
  },
  cardSummary:
    "The dollar-centred order is fracturing at the margin, not rupturing. USD " +
    "reserve share is drifting lower, central banks are accumulating gold at a " +
    "record pace, and the US shows classic late-empire markers — high debt, " +
    "internal division, external rivalry.",
  scorecard: {
    label: "Section A — reserve-status & empire scorecard",
    rows: [
      {
        name: "USD share of global FX reserves",
        sub: "IMF COFER-style, allocated",
        current: "57%",
        currentTone: "amber",
        currentMeta: "down from ~72% in 2000",
        fillPct: 57,
        fillTone: "amber",
        trend: "declining ~0.5pp/yr",
        signalLabel: "Eroding",
        signalTone: "amber",
      },
      {
        name: "Net central bank gold purchases",
        sub: "Official sector, annualised",
        current: "+1,040t",
        currentTone: "green",
        currentMeta: "record multi-year pace",
        fillPct: 84,
        fillTone: "green",
        trend: "3rd straight >1,000t year",
        signalLabel: "Accumulating",
        signalTone: "green",
      },
      {
        name: "Foreign Treasury holdings trend",
        sub: "Official + private, share of debt",
        current: "22%",
        currentTone: "amber",
        currentMeta: "down from ~34% in 2013",
        fillPct: 48,
        fillTone: "amber",
        trend: "domestic buyers taking share",
        signalLabel: "Diversifying",
        signalTone: "amber",
      },
      {
        name: "Dollar Index (DXY)",
        sub: "Trade-weighted USD",
        current: "101.4",
        currentTone: "blue",
        currentMeta: "range-bound, off highs",
        fillPct: 52,
        fillTone: "blue",
        trend: "softening with cuts",
        signalLabel: "Neutral",
        signalTone: "blue",
      },
      {
        name: "Internal cohesion index",
        sub: "Political polarisation proxy",
        current: "Elevated",
        currentTone: "red",
        currentMeta: "near multi-decade highs",
        fillPct: 78,
        fillTone: "red",
        trend: "rising",
        signalLabel: "Late-empire",
        signalTone: "red",
      },
    ],
  },
  reserveChart: {
    title: "Reserve-currency share over time (illustrative)",
    years: [2000, 2005, 2010, 2015, 2020, 2026],
    series: [
      { label: "USD", values: [72, 66, 62, 65, 59, 57], isPrimary: true },
      { label: "EUR", values: [18, 24, 26, 19, 21, 20] },
      { label: "JPY", values: [6, 4, 4, 4, 6, 6] },
      { label: "CNY", values: [0, 0, 0, 1, 2, 3] },
    ],
  },
  empireCycle: {
    label: "Section B",
    stripTitle: "Where the US sits on the empire arc",
    stages: [
      { num: "1", name: "New order rises", range: "1945", state: "past", weight: 1 },
      { num: "2", name: "Peak & reserve status", range: "1945-71", state: "past", weight: 2 },
      { num: "3", name: "Debt-financed excess", range: "1971-2008", state: "past", weight: 3 },
      { num: "4", name: "Financialisation & gap", range: "2008-20", state: "past", weight: 4 },
      { num: "5", name: "Debt + internal conflict", range: "now", state: "active" },
      { num: "6", name: "Order change", range: "ahead", state: "future" },
    ],
    quote: {
      title: "The archetype",
      body:
        "Empires decline when they take on more debt than they can service, when " +
        "internal wealth gaps drive political conflict, and when a rising rival " +
        "challenges the incumbent — the three big forces turning together.",
      attribution: "Dalio archetype — paraphrased for this demo",
      tone: "amber",
    },
    markersTitle: "Late-empire markers now present",
    markers: [
      { tone: "red", pillLabel: "Debt", leadPhrase: "Debt burden binding.", body: "Interest costs crowd the fiscal path (see T1)." },
      { tone: "red", pillLabel: "Internal", leadPhrase: "Wealth gap wide.", body: "Polarisation near multi-decade highs." },
      { tone: "amber", pillLabel: "External", leadPhrase: "Rival rising.", body: "A peer competitor contests trade, tech and reserve status." },
      { tone: "green", pillLabel: "Reserve", leadPhrase: "Still incumbent.", body: "USD remains dominant — erosion is gradual, not sudden." },
    ],
  },
  analogs: {
    label: "Section C",
    cells: [
      { era: "Dutch guilder → 1780s", tone: "amber", body: "Reserve status faded slowly, then over debt and war — decades, not months." },
      { era: "Sterling → 1914-45", tone: "amber", body: "Two wars and debt eroded the pound; the transition took a full generation." },
      { era: "USD → today", tone: "blue", body: "Early in the analogous window: markers present, dominance still intact." },
    ],
  },
  wealthShift: {
    label: "Section C2",
    intro:
      "Beneath the reserve-share number, capital and production are shifting — the " +
      "slow redistribution that late-empire cycles produce.",
    rows: [
      { tone: "amber", pillLabel: "Flows", leadPhrase: "Reserve diversification.", body: "Managers add gold and non-USD assets at the margin." },
      { tone: "amber", pillLabel: "Production", leadPhrase: "Supply-chain reshoring.", body: "Manufacturing re-regionalises around blocs." },
      { tone: "green", pillLabel: "Gold", leadPhrase: "Official-sector bid.", body: "Central banks treat gold as the neutral reserve asset." },
    ],
    assessment: {
      title: "Assessment — a gradual repricing, not a rupture",
      body:
        "The wealth shift is real but slow. It argues for owning the neutral reserve " +
        "asset (gold) and diversifying currency exposure over time — not for betting " +
        "on an abrupt collapse of the dollar system.",
    },
  },
  investment: {
    label: "Section D",
    goldRange: {
      title: "Gold as the neutral reserve",
      stats: [
        { label: "Spot", value: "$2,940", highlight: true },
        { label: "CB demand", value: "+1,040t", highlight: false },
        { label: "Confluence wt", value: "~12%", highlight: false },
      ],
      body:
        "With the official sector itself diversifying into gold, the structural bid " +
        "is a policy signal, not a speculative one. Gold is the asset the world-order " +
        "lens and the debt-cycle lens agree on.",
    },
    currency: {
      title: "Currency exposure",
      rows: [
        { name: "USD", badgeLabel: "Reduce at margin", badgeTone: "amber", body: "Still dominant, but trim over-concentration over time." },
        { name: "Gold", badgeLabel: "Add", badgeTone: "green", body: "The neutral reserve; the official-sector bid is structural." },
        { name: "EUR / JPY", badgeLabel: "Diversify", badgeTone: "blue", body: "Modest allocation as reserve share fragments." },
        { name: "CNY", badgeLabel: "Watch", badgeTone: "amber", body: "Rising slowly; capital-account frictions cap the pace." },
      ],
    },
    sovereignBond: {
      title: "Sovereign-bond premium",
      intro:
        "As reserve status erodes and supply grows, holders demand more term premium " +
        "to fund the incumbent — the World Order channel into the Debt Cycle.",
      pair: {
        left: { title: "Term premium rebuild", body: "The long end must pay more as the marginal foreign buyer steps back — bearish long duration." },
        right: { title: "Front-end refuge", body: "The cutting cycle anchors the front end; own 2-5y for carry without the supply tax." },
      },
    },
  },
  verdict: {
    title: "Late-empire markers present, dominance intact — own the neutral reserve",
    body:
      "The US shows the classic late-empire triad — binding debt, internal division, " +
      "external rivalry — while the dollar remains the incumbent reserve. The " +
      "rational response is gradual: accumulate the neutral reserve asset (gold), " +
      "diversify currency exposure at the margin, and price a rebuilding term " +
      "premium into long-duration sovereign risk.",
    tone: "amber",
  },
  sources: SOURCES,
};

// ===========================================================================
// T5 — FIVE FORCES  (FiveForcesData)
// ===========================================================================

const FIVE_FORCES: FiveForcesData = {
  header: {
    title: "The Five Big Forces",
    subtitle: "T5 · Debt, internal conflict, external conflict, nature, technology",
    badges: [
      { tone: "red", label: "3 of 5 elevated" },
      { tone: "amber", label: "Loops reinforcing" },
      { tone: "blue", label: "Tech is the wildcard" },
    ],
  },
  cardSummary:
    "Three of the five big forces — debt, internal conflict and external conflict " +
    "— are running hot and their reinforcement loops are live. Nature is moderate; " +
    "technology is the two-sided wildcard that could relieve or amplify the rest.",
  scorecard: {
    label: "5 forces",
    rows: [
      {
        forceLabel: "01",
        forceSub: "Debt & money",
        pillTone: "red",
        pillLabel: "Elevated",
        scorePct: 82,
        scoreTone: "red",
        scoreValue: "8.2 / 10",
        body:
          "**Binding.** Debt service near cycle highs and real yields above trend " +
          "growth (see T1). The primary transmitter into every other force.",
      },
      {
        forceLabel: "02",
        forceSub: "Internal conflict",
        pillTone: "red",
        pillLabel: "Elevated",
        scorePct: 74,
        scoreTone: "red",
        scoreValue: "7.4 / 10",
        body:
          "**Hot.** Wealth and political gaps near multi-decade wides; fiscal " +
          "constraints sharpen distributional fights.",
      },
      {
        forceLabel: "03",
        forceSub: "External conflict",
        pillTone: "amber",
        pillLabel: "Rising",
        scorePct: 71,
        scoreTone: "amber",
        scoreValue: "7.1 / 10",
        body:
          "**Rising.** A peer rivalry over trade, tech and reserve status (see T4) " +
          "keeps geopolitical risk premia elevated.",
      },
      {
        forceLabel: "04",
        forceSub: "Acts of nature",
        pillTone: "amber",
        pillLabel: "Moderate",
        scorePct: 46,
        scoreTone: "amber",
        scoreValue: "4.6 / 10",
        body:
          "**Moderate.** Climate and supply-shock risk is a persistent tax on " +
          "inflation volatility but not currently acute.",
      },
      {
        forceLabel: "05",
        forceSub: "Technology",
        pillTone: "blue",
        pillLabel: "Two-sided",
        scorePct: 55,
        scoreTone: "blue",
        scoreValue: "5.5 / 10",
        body:
          "**Wildcard.** An AI-driven productivity boom could relieve the debt force " +
          "via growth — or concentrate wealth and worsen the internal one.",
      },
    ],
  },
  loops: {
    label: "3 active loops",
    blocks: [
      {
        title: "Debt → Internal conflict",
        arrows: [
          { fromLabel: "Debt service ↑", toLabel: "Fiscal squeeze" },
          { fromLabel: "Fiscal squeeze", toLabel: "Distributional fight" },
        ],
        body:
          "Rising interest costs shrink discretionary fiscal space, sharpening the " +
          "fight over who bears the adjustment — a live, self-reinforcing loop.",
      },
      {
        title: "External → Debt",
        arrows: [
          { fromLabel: "Rivalry ↑", toLabel: "Reserve diversification" },
          { fromLabel: "Fewer foreign buyers", toLabel: "Higher term premium" },
        ],
        body:
          "Geopolitical rivalry accelerates reserve diversification (T4), thinning " +
          "the foreign bid for Treasuries and raising the cost to fund the debt.",
      },
      {
        title: "Technology → all (relief valve)",
        arrows: [
          { fromLabel: "Productivity ↑", toLabel: "Growth ↑" },
          { fromLabel: "Growth ↑", toLabel: "Debt burden ↓" },
        ],
        body:
          "The one loop that can run in reverse: a genuine productivity boom lifts " +
          "growth and eases the debt force — the bullish tail for the whole system.",
      },
    ],
    active: {
      countText: "3",
      countTone: "red",
      title: "Three loops active and reinforcing",
      body:
        "The debt, internal-conflict and external-conflict forces are feeding each " +
        "other rather than offsetting. Aggregate stress sits in the amber-red band; " +
        "technology is the only force that could break the cycle constructively.",
    },
    network: {
      label: "Force transmission network",
      edges: [
        { fromLabel: "Debt", toLabel: "Internal", strength: 0.72 },
        { fromLabel: "External", toLabel: "Debt", strength: 0.61 },
        { fromLabel: "Internal", toLabel: "External", strength: 0.44 },
        { fromLabel: "Nature", toLabel: "Debt", strength: 0.28 },
      ],
      projections: [
        { force: "Debt & money", current: 8.2, projected: 8.5, delta: 0.3 },
        { force: "Internal conflict", current: 7.4, projected: 7.7, delta: 0.3 },
        { force: "External conflict", current: 7.1, projected: 7.3, delta: 0.2 },
        { force: "Acts of nature", current: 4.6, projected: 4.7, delta: 0.1 },
        { force: "Technology", current: 5.5, projected: 5.2, delta: -0.3 },
      ],
      amplifier: "Debt & money — transmits to every other force",
      absorber: "Technology — the only force that can dampen the rest",
      contagion: 0.68,
      contagionLabel: "High",
    },
  },
  signals: {
    label: "Section C",
    cards: [
      { label: "HY credit spread", value: "348", unit: "bp OAS", note: "Tight-but-orderly; a break >500bp lights the debt loop." },
      { label: "Term premium", value: "+0.42%", unit: "10Y ACM-style", note: "Rebuilding as the foreign bid thins (T4)." },
      { label: "Geopolitical risk", value: "Elevated", unit: "GPR-style index", note: "External-conflict force keeping premia up." },
      { label: "Gold / real rate", value: "Decoupled", unit: "beta breaking", note: "Gold rising despite positive real rates — the tell." },
      { label: "Policy uncertainty", value: "High", unit: "EPU-style", note: "Fiscal fights raise the internal-conflict reading." },
      { label: "AI capex", value: "Surging", unit: "% of S&P capex", note: "The technology relief-valve, still speculative." },
    ],
  },
  goldAllocation: {
    label: "Section D",
    block: {
      title: "Gold allocation under a multi-force regime",
      ticks: ["0%", "5%", "7.5%", "10%", "12%", "15%+"],
      stats: [
        { label: "Base weight", value: "5%", note: "A neutral starting sleeve.", highlight: false },
        { label: "Force-adjusted", value: "~12%", note: "Lifted by 3 elevated forces + live loops.", highlight: true },
        { label: "Rationale", value: "Confluence", note: "T1 debt + T4 order + T5 forces all agree.", highlight: false },
      ],
      body:
        "With three forces elevated and their loops reinforcing, the framework lifts " +
        "the gold sleeve well above a static base — gold is the asset that pays off " +
        "across the debt, conflict and reserve-erosion channels simultaneously.",
    },
  },
  scenarios: {
    label: "Section E",
    cards: [
      {
        variant: "bull",
        title: "Technology breaks the loop",
        body:
          "An AI-led productivity boom lifts trend growth, shrinks the debt burden " +
          "relative to output, and de-escalates the distributional fight — the " +
          "constructive tail where the forces relax together.",
      },
      {
        variant: "bear",
        title: "Loops go acute",
        body:
          "Credit spreads break out, foreign buyers step further back, and fiscal " +
          "fights harden — the debt, internal and external forces spiral, forcing " +
          "the monetisation valve open and accelerating the debasement path.",
      },
    ],
  },
  verdict: {
    title: "Three forces hot, loops live — technology is the only offramp",
    body:
      "Debt, internal conflict and external conflict are elevated and reinforcing, " +
      "putting aggregate systemic stress in the amber-red band. The single force " +
      "that can break the cycle constructively is technology-driven productivity; " +
      "until it shows through in the data, the framework favours owning gold and " +
      "real assets that pay off across every channel at once.",
  },
  sources: SOURCES,
};

// ---------------------------------------------------------------------------
// Payload registry: slug -> typed payload. Every dashboard is fully populated.
// ---------------------------------------------------------------------------

const PAYLOAD_BY_SLUG: Record<string, unknown> = {
  summary: SUMMARY,
  debt_cycle: DEBT_CYCLE,
  four_seasons: FOUR_SEASONS,
  all_weather: ALL_WEATHER,
  world_order: WORLD_ORDER,
  five_forces: FIVE_FORCES,
};

function dashboardResponse(slug: string): DashboardResponse<unknown> {
  return {
    payload: PAYLOAD_BY_SLUG[slug] ?? null,
    generated_at: GENERATED_AT,
    is_stale: false,
    provenance: PROVENANCE,
  };
}

// Read-only demo: a stray refresh returns a benign queued result. The view's
// poll immediately re-fetches the already-populated dashboard and settles.
const REFRESH_RESULT: RunAssessmentResult = {
  job_run_id: "mr-demo-refresh-0807",
  status: "queued",
};

// Auto cadence == no persisted cron (live in-session polling only).
const SCHEDULE: ScheduleState = {
  cron_expression: null,
  last_assessment_at: GENERATED_AT,
};

// ---------------------------------------------------------------------------
// REST routes
// ---------------------------------------------------------------------------

register([
  // Framework list (page tab row). Summary is filtered out by the page itself.
  {
    method: "GET",
    pattern: `${BASE}/dashboards`,
    handler: () => json({ dashboards: DASHBOARDS }),
  },

  // Per-dashboard cached state (Summary + each framework view).
  {
    method: "GET",
    pattern: `${BASE}/dashboards/:slug`,
    handler: (req) => {
      const slug = req.params.slug;
      if (!(slug in PAYLOAD_BY_SLUG)) return notFound();
      return json(dashboardResponse(slug));
    },
  },

  // Refresh / run assessment — benign queued result (read-only demo).
  {
    method: "POST",
    pattern: `${BASE}/dashboards/:slug/refresh`,
    handler: (req) =>
      req.params.slug in PAYLOAD_BY_SLUG ? json(REFRESH_RESULT) : notFound(),
  },

  // Refresh cadence schedule (header dropdown reads GET, writes PUT/DELETE).
  {
    method: "GET",
    pattern: `${BASE}/schedule`,
    handler: () => json(SCHEDULE),
  },
  {
    method: "PUT",
    pattern: `${BASE}/schedule`,
    handler: (req) => {
      const body = (req.body ?? {}) as { cron_expression?: string | null };
      return json({
        cron_expression: body.cron_expression ?? null,
        last_assessment_at: GENERATED_AT,
      } satisfies ScheduleState);
    },
  },
  {
    method: "DELETE",
    pattern: `${BASE}/schedule`,
    handler: () => json(null, 204),
  },
]);

export { DEMO_NOW_ISO };
