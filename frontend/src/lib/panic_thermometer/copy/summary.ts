import type { HeroCopy, ScorecardEntry, SummaryStats } from "./types";

export const summaryStats: SummaryStats = {
  composite: "severe",
  scoreOutOf5: 3.2,
  redCount: 3,
  totalPanels: 5,
  delta7day: 1,
  lastRefreshIso: "2026-05-04T10:48:00Z",
  lastRefreshLabel: "06:48 ET",
  trend: "widening",
  asOfDateLabel: "Live · MON 04 MAY 2026",
};

export const heroCopy: HeroCopy = {
  eyebrowTime: "Panic Thermometer · 06:48 ET",
  headline: "Three of five indicators red.",
  accent:
    "Wage spiral and Fed hawkish pivot driving the move; oil duration extending.",
  ledeFragments: [
    { kind: "text", value: "Brent has held above your " },
    { kind: "strong", value: "$85 threshold" },
    { kind: "text", value: " for " },
    { kind: "hot", value: "47 consecutive sessions" },
    {
      kind: "text",
      value:
        " — past the 30-day amber line, two-thirds of the way to the 2022-playbook trigger. April AHE printed ",
    },
    { kind: "hot", value: "+0.6% MoM" },
    {
      kind: "text",
      value: ' for the second straight month. Powell dropped "patient" from the 30 Apr presser. Disinflation expectations ',
    },
    { kind: "warm", value: "drifting" },
    { kind: "text", value: " at 2.9%. Diplomacy window has 8 days remaining." },
  ],
  thermBulbFillPct: 80,
  scale: [
    { severity: "calm", label: "Calm", detail: "0 red", reachedOn: null },
    { severity: "elevated", label: "Elevated", detail: "1 red", reachedOn: null },
    { severity: "high", label: "High", detail: "2 red", reachedOn: "25 Apr" },
    {
      severity: "severe",
      label: "Severe",
      detail: "3+ red",
      reachedOn: "▶ today",
      isCurrent: true,
    },
    { severity: "crisis", label: "Crisis", detail: "4+ red", reachedOn: null },
  ],
};

export const scorecards: ScorecardEntry[] = [
  {
    panelId: "oil",
    index: "D1 · OIL",
    title: "Oil price duration",
    status: "red",
    stampLabel: "Red",
    primaryValue: "47",
    primaryUnit: "days",
    miniChart: {
      kind: "spark-area",
      points: [22, 20, 16, 18, 14, 12, 10, 11, 8, 9, 7, 5, 6],
      threshold: 14,
    },
    detail: [
      { kind: "text", value: "BNO " },
      { kind: "strong", value: "$48.20" },
      { kind: "text", value: " · above " },
      { kind: "strong", value: "$45.00", tone: "bad" },
      { kind: "text", value: " threshold · 17 days from " },
      { kind: "strong", value: "2022 trigger", tone: "bad" },
    ],
  },
  {
    panelId: "inflation",
    index: "D2 · INFL",
    title: "Inflation expectations",
    status: "amber",
    stampLabel: "Amber",
    primaryValue: "2.9",
    primaryUnit: "%",
    miniChart: {
      kind: "spark-area",
      points: [18, 17, 16, 15, 14, 13, 12, 10, 9],
    },
    detail: [
      { kind: "text", value: "Michigan 5Y " },
      { kind: "strong", value: "2.9%" },
      { kind: "text", value: " · TIP slope " },
      { kind: "strong", value: "+0.04", tone: "warn" },
      { kind: "text", value: "/d · 0.1pp from " },
      { kind: "strong", value: "red" },
    ],
  },
  {
    panelId: "fed",
    index: "D3 · FED",
    title: "Fed language tracker",
    status: "red",
    stampLabel: "Red",
    primaryValue: "Hawkish",
    miniChart: {
      kind: "stripe-bars",
      stripes: [
        { status: "green", intensity: 0.3 },
        { status: "green", intensity: 0.3 },
        { status: "neutral", intensity: 0.5 },
        { status: "red", intensity: 1 },
        { status: "darkred", intensity: 0.25 },
      ],
    },
    detail: [
      { kind: "text", value: "Powell " },
      { kind: "strong", value: '"persistent inflation"', tone: "bad" },
      { kind: "text", value: " · 30 Apr · 4 days post-FOMC" },
    ],
  },
  {
    panelId: "wage",
    index: "D4 · WAGE",
    title: "Wage growth (AHE)",
    status: "darkred",
    stampLabel: "Dark red",
    primaryValue: "+0.6",
    primaryUnit: "% MoM",
    miniChart: {
      kind: "bars",
      bars: [
        { value: 8, status: "green" },
        { value: 10, status: "green" },
        { value: 12, status: "green" },
        { value: 14, status: "amber" },
        { value: 13, status: "amber" },
        { value: 15, status: "amber" },
        { value: 17, status: "red" },
        { value: 20, status: "darkred" },
        { value: 21, status: "darkred" },
      ],
      threshold: 18,
    },
    detail: [
      { kind: "text", value: "2 consecutive months > " },
      { kind: "strong", value: "0.5%", tone: "bad" },
      { kind: "text", value: " · spiral risk · prev " },
      { kind: "strong", value: "0.6%" },
    ],
  },
  {
    panelId: "diplomacy",
    index: "D5 · DIPL",
    title: "Diplomatic progress",
    status: "amber",
    stampLabel: "Amber",
    primaryValue: "22",
    primaryUnit: "/30 d",
    miniChart: {
      kind: "progress",
      progressPct: 73,
    },
    detail: [
      { kind: "text", value: "8 days remaining · last milestone " },
      { kind: "strong", value: "11 Apr" },
      { kind: "text", value: " · no escalation kw" },
    ],
  },
];
