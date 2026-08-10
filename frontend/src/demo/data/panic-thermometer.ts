// Panic Thermometer demo data. This department is a stateless formula engine
// (no LLM): the dashboard GETs five stress-panel evaluations + a composite
// threat level, and the settings drawer reads the user-editable rule/parameter
// config plus saved presets. Every write endpoint (config save/import, preset
// CRUD/apply, formula parse/test, ruleset preview) is READ-ONLY in the demo and
// returns a plausible benign payload.
//
// Base path: /api/departments/panic_thermometer (see src/api/panic-thermometer.ts).
// All numbers are illustrative and internally consistent with a coherent
// "elevated · 1 amber, 0 red" reading anchored on the frozen demo clock.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, hoursAgo } from "../clock";
import type {
  CompositeSettings,
  DashboardPayload,
  PanelConfig,
  PanelResult,
  PtPreset,
  UserConfig,
} from "../../api/panic-thermometer";

const BASE = "/api/departments/panic_thermometer";

// --------------------------------------------------------------------------
// Series builders (deterministic, gently varying)
// --------------------------------------------------------------------------

/** Smooth pseudo-random walk around `base` for chart backdrops. */
function series(base: number, points: number, amp: number, drift = 0): number[] {
  return Array.from({ length: points }, (_, i) => {
    const wobble = Math.sin(i * 0.7) * amp + Math.cos(i * 0.31) * amp * 0.4;
    return Math.round((base + drift * i + wobble) * 100) / 100;
  });
}

// WTI holding just above its $80 threshold for a handful of sessions -> green,
// short streak. Latest close $82.40.
const OIL_PRICE_SERIES: number[] = [
  76.1, 75.4, 77.2, 78.9, 79.3, 78.1, 79.6, 80.4, 81.1, 80.7, 81.9, 82.4,
];
const OIL_STREAK_DAYS = 4; // sessions above the $80 threshold

// TIP ETF (inflation-protected) price series backing the inflation panel.
const TIP_SERIES: number[] = series(108.5, 12, 0.6, 0.05);

// AHE month-over-month prints (%), latest run cooling back under the amber line.
const WAGE_SERIES: number[] = [
  0.31, 0.28, 0.42, 0.39, 0.33, 0.35, 0.41, 0.38, 0.3, 0.34, 0.36, 0.33,
];

// --------------------------------------------------------------------------
// Panel evaluations
// --------------------------------------------------------------------------

const oilPanel: PanelResult = {
  panel_id: "oil",
  status: "green",
  label: "Below duration threshold",
  resolved_values: {
    price: 82.4,
    streak_days: OIL_STREAK_DAYS,
    threshold: 80,
  },
  derived_scalars: {
    ma_20: 79.8,
    ma_50: 77.6,
    pct_above_threshold: 3.0,
  },
  extras: {
    price: 82.4,
    streak_days: OIL_STREAK_DAYS,
    latest_close_date: hoursAgo(19),
    ma_20: 79.8,
    ma_50: 77.6,
  },
  raw_series: {
    price: OIL_PRICE_SERIES,
    ma_20: series(79.5, 12, 0.3, 0.08),
  },
  params: {
    ticker: "CL.COMM",
    price_threshold: 80,
    streak_amber: 1,
    streak_red: 30,
    streak_dark_red: 90,
    ma_window: 20,
  },
  warnings: [],
};

// Inflation is the single amber panel: Michigan 5y at 3.1% sits above the 2.5%
// amber line but below the 3.5% red line.
const inflationPanel: PanelResult = {
  panel_id: "inflation",
  status: "amber",
  label: "Above amber, below red",
  resolved_values: {
    michigan_5y: 3.1,
    tip_price: 108.9,
  },
  derived_scalars: {
    michigan_delta_mom: 0.2,
    tip_ma_20: 108.3,
  },
  extras: {
    michigan_5y: 3.1,
    michigan_prev: 2.9,
    michigan_5y_missing: false,
    tip_price_latest: 108.9,
    survey_date: hoursAgo(30),
  },
  raw_series: {
    tip_price: TIP_SERIES,
  },
  params: {
    michigan_ticker: "UMCSENT",
    tip_ticker: "TIP.US",
    level_amber: 2.5,
    level_red: 3.5,
    level_dark_red: 4.0,
  },
  warnings: [],
};

// Fed language reads neutral: no hawkish/dovish/crisis trigger in the recent
// FOMC + newsflow window.
const fedPanel: PanelResult = {
  panel_id: "fed_language",
  status: "green",
  label: "Neutral posture",
  resolved_values: {
    tone: "neutral",
  },
  derived_scalars: {
    days_since_fomc: 12,
  },
  extras: {
    dovish_keyword_detected: false,
    hawkish_keyword_detected: false,
    crisis_keyword_detected: false,
    matched_phrase: "data-dependent, no pre-set path",
    matched_headline:
      "Fed holds rates steady, reiterates data-dependent, no pre-set path",
    matched_date: hoursAgo(52),
    days_since_fomc: 12,
  },
  raw_series: {},
  params: {
    news_lookback_days: 14,
    dovish_keywords: ["accommodative", "cut", "easing", "patient"],
    neutral_keywords: ["data-dependent", "steady", "balanced", "monitor"],
    hawkish_keywords: ["restrictive", "hike", "tighten", "vigilant"],
    crisis_keywords: ["emergency", "intermeeting", "unlimited", "backstop"],
  },
  warnings: [],
};

// Wage growth green: latest AHE +0.3% MoM, only 0 of the required 2 consecutive
// hot prints above the 0.4% amber line.
const wagePanel: PanelResult = {
  panel_id: "wage_growth",
  status: "green",
  label: "Below spiral threshold",
  resolved_values: {
    value: 0.33,
    consecutive_count: 0,
  },
  derived_scalars: {
    avg_12m: 0.35,
    prev_value: 0.36,
  },
  extras: {
    value: 0.33,
    prev_value: 0.36,
    consecutive_count: 0,
    avg_12m: 0.35,
    release_date: hoursAgo(46),
  },
  raw_series: {
    value: WAGE_SERIES,
  },
  params: {
    ticker: "CES0500000003",
    wage_threshold_amber: 0.4,
    wage_threshold_red: 0.5,
    consecutive_required: 2,
  },
  warnings: [],
};

// Diplomacy green: 62-day negotiation window, day 24 of 90, no escalation.
const diplomacyPanel: PanelResult = {
  panel_id: "diplomacy",
  status: "green",
  label: "Window open, no escalation",
  resolved_values: {
    days_elapsed: 24,
    days_remaining: 66,
  },
  derived_scalars: {
    progress_signal_count: 2,
    escalation_signal_count: 0,
  },
  extras: {
    days_elapsed: 24,
    days_remaining: 66,
    progress_detected: true,
    escalation_detected: false,
    matched_progress_headlines: [
      "Delegations agree to extend ceasefire talks another two weeks",
      "Working group reports tentative deal on prisoner exchange",
    ],
    matched_escalation_headlines: [],
    milestone_date: null,
  },
  raw_series: {},
  params: {
    window_days: 90,
    progress_keywords: ["ceasefire", "agreement", "talks", "deal"],
    escalation_keywords: ["strike", "mobilize", "withdraw", "sanction"],
  },
  warnings: [],
};

const DASHBOARD: DashboardPayload = {
  panels: {
    oil: oilPanel,
    inflation: inflationPanel,
    fed_language: fedPanel,
    wage_growth: wagePanel,
    diplomacy: diplomacyPanel,
  },
  // Composite: count mode, 0 red / 1 amber -> Elevated. Score 1.2 / 5.0.
  composite: {
    level: "elevated",
    score: 1.2,
    red_count: 0,
    mode: "count",
  },
  generated_at: DEMO_NOW_ISO,
  warnings: [],
};

// --------------------------------------------------------------------------
// User config (rule/parameter viewer + composite aggregation settings)
// --------------------------------------------------------------------------

const COMPOSITE_SETTINGS: CompositeSettings = {
  mode: "count",
  red_threshold: 1,
  weights: {
    oil: 1,
    inflation: 1,
    fed_language: 1,
    wage_growth: 1,
    diplomacy: 1,
  },
  thresholds: {
    calm: 0,
    elevated: 1,
    high: 2,
    severe: 3,
    crisis: 4,
  },
  refresh_interval_minutes: 5,
};

const PANEL_CONFIG: PanelConfig[] = [
  {
    panel_id: "oil",
    rules: [
      {
        status: "dark_red",
        formula: "streak_days >= streak_dark_red",
        label: "Sustained 90+ session stress",
      },
      {
        status: "red",
        formula: "streak_days >= streak_red",
        label: "Elevated 30+ session stress",
      },
      {
        status: "amber",
        formula: "streak_days >= streak_amber and price >= price_threshold",
        label: "Above amber, below red",
      },
      {
        status: "green",
        formula: "price < price_threshold",
        label: "Below duration threshold",
      },
    ],
    params: {
      ticker: "CL.COMM",
      price_threshold: 80,
      streak_amber: 1,
      streak_red: 30,
      streak_dark_red: 90,
      ma_window: 20,
    },
    streak_condition: "price >= price_threshold",
    manual_override: null,
    milestone_date: null,
    enabled: true,
  },
  {
    panel_id: "inflation",
    rules: [
      {
        status: "dark_red",
        formula: "michigan_5y >= level_dark_red",
        label: "Expectations unanchored",
      },
      {
        status: "red",
        formula: "michigan_5y >= level_red",
        label: "Above red line",
      },
      {
        status: "amber",
        formula: "michigan_5y >= level_amber",
        label: "Above amber, below red",
      },
      { status: "green", formula: "michigan_5y < level_amber", label: "Anchored" },
    ],
    params: {
      michigan_ticker: "UMCSENT",
      tip_ticker: "TIP.US",
      level_amber: 2.5,
      level_red: 3.5,
      level_dark_red: 4.0,
    },
    streak_condition: null,
    manual_override: null,
    milestone_date: null,
    enabled: true,
  },
  {
    panel_id: "fed_language",
    rules: [
      {
        status: "dark_red",
        formula: "crisis_keyword_detected",
        label: "Crisis language",
      },
      {
        status: "red",
        formula: "hawkish_keyword_detected",
        label: "Hawkish posture",
      },
      {
        status: "green",
        formula: "not hawkish_keyword_detected",
        label: "Neutral or dovish posture",
      },
    ],
    params: {
      news_lookback_days: 14,
      dovish_keywords: ["accommodative", "cut", "easing", "patient"],
      neutral_keywords: ["data-dependent", "steady", "balanced", "monitor"],
      hawkish_keywords: ["restrictive", "hike", "tighten", "vigilant"],
      crisis_keywords: ["emergency", "intermeeting", "unlimited", "backstop"],
    },
    streak_condition: null,
    manual_override: null,
    milestone_date: null,
    enabled: true,
  },
  {
    panel_id: "wage_growth",
    rules: [
      {
        status: "dark_red",
        formula: "consecutive_count >= consecutive_required and value >= wage_threshold_red",
        label: "Sustained wage-price spiral",
      },
      {
        status: "red",
        formula: "value >= wage_threshold_red",
        label: "Hot single print",
      },
      {
        status: "amber",
        formula: "value >= wage_threshold_amber",
        label: "Above amber line",
      },
      {
        status: "green",
        formula: "value < wage_threshold_amber",
        label: "Below spiral threshold",
      },
    ],
    params: {
      ticker: "CES0500000003",
      wage_threshold_amber: 0.4,
      wage_threshold_red: 0.5,
      consecutive_required: 2,
    },
    streak_condition: "value >= wage_threshold_amber",
    manual_override: null,
    milestone_date: null,
    enabled: true,
  },
  {
    panel_id: "diplomacy",
    rules: [
      {
        status: "dark_red",
        formula: "escalation_detected and days_remaining <= 0",
        label: "Escalation with window closed",
      },
      {
        status: "red",
        formula: "escalation_detected",
        label: "Escalation signal",
      },
      {
        status: "amber",
        formula: "days_remaining <= 15 and not progress_detected",
        label: "Window closing without progress",
      },
      {
        status: "green",
        formula: "progress_detected or days_remaining > 15",
        label: "Window open, no escalation",
      },
    ],
    params: {
      window_days: 90,
      progress_keywords: ["ceasefire", "agreement", "talks", "deal"],
      escalation_keywords: ["strike", "mobilize", "withdraw", "sanction"],
    },
    streak_condition: null,
    manual_override: null,
    milestone_date: null,
    enabled: true,
  },
];

const USER_CONFIG: UserConfig = {
  id: "demo-pt-config",
  panel_config: PANEL_CONFIG,
  composite_settings: COMPOSITE_SETTINGS,
  active_preset_id: "preset-report-defaults",
};

// --------------------------------------------------------------------------
// Presets
// --------------------------------------------------------------------------

const PRESETS: PtPreset[] = [
  {
    id: "preset-report-defaults",
    user_id: null,
    name: "Report defaults",
    description: "Ships-with thresholds tuned for a macro desk.",
    is_shipped: true,
  },
  {
    id: "preset-hair-trigger",
    user_id: null,
    name: "Hair trigger",
    description: "Tighter amber/red lines for early-warning bias.",
    is_shipped: true,
  },
  {
    id: "preset-my-desk",
    user_id: "demo-user",
    name: "My desk",
    description: "Weighted composite favouring inflation and Fed panels.",
    is_shipped: false,
  },
];

// --------------------------------------------------------------------------
// Routes
// --------------------------------------------------------------------------

register([
  // Dashboard: five panel evaluations + composite roll-up.
  {
    method: "GET",
    pattern: `${BASE}/dashboard`,
    handler: () => json(DASHBOARD),
  },

  // Config: rule/parameter viewer + composite aggregation settings.
  {
    method: "GET",
    pattern: `${BASE}/config`,
    handler: () => json(USER_CONFIG),
  },
  // Read-only: echo the submitted config back merged onto the base shape.
  {
    method: "PUT",
    pattern: `${BASE}/config`,
    handler: (req) => {
      const b = (req.body ?? {}) as Partial<
        Pick<UserConfig, "panel_config" | "composite_settings">
      >;
      return json({
        ...USER_CONFIG,
        panel_config: b.panel_config ?? USER_CONFIG.panel_config,
        composite_settings: b.composite_settings ?? USER_CONFIG.composite_settings,
      } satisfies UserConfig);
    },
  },
  {
    method: "GET",
    pattern: `${BASE}/config/export`,
    handler: () =>
      json({
        version: 1,
        panel_config: PANEL_CONFIG,
        composite_settings: COMPOSITE_SETTINGS,
      }),
  },
  // Read-only: importing a shared config is a no-op that returns current state.
  {
    method: "POST",
    pattern: `${BASE}/config/import`,
    handler: () => json(USER_CONFIG),
  },

  // Presets: list + read-only CRUD/apply.
  {
    method: "GET",
    pattern: `${BASE}/presets`,
    handler: () => json(PRESETS),
  },
  {
    method: "POST",
    pattern: `${BASE}/presets`,
    handler: (req) => {
      const b = (req.body ?? {}) as { name?: string; description?: string | null };
      return json({
        id: "preset-new-demo",
        user_id: "demo-user",
        name: b.name ?? "New preset",
        description: b.description ?? null,
        is_shipped: false,
      } satisfies PtPreset);
    },
  },
  {
    method: "PUT",
    pattern: `${BASE}/presets/:id`,
    handler: (req) => {
      const b = (req.body ?? {}) as { name?: string; description?: string | null };
      const existing = PRESETS.find((p) => p.id === req.params.id);
      if (!existing) return notFound();
      return json({
        ...existing,
        name: b.name ?? existing.name,
        description: b.description ?? existing.description,
      } satisfies PtPreset);
    },
  },
  {
    method: "DELETE",
    pattern: `${BASE}/presets/:id`,
    handler: () => json(null),
  },
  // Read-only: applying a preset returns the current config unchanged.
  {
    method: "POST",
    pattern: `${BASE}/presets/:id/apply`,
    handler: (req) => {
      if (!PRESETS.some((p) => p.id === req.params.id)) return notFound();
      return json({ ...USER_CONFIG, active_preset_id: req.params.id } satisfies UserConfig);
    },
  },

  // Formula tooling: benign successful parse/test/preview.
  {
    method: "POST",
    pattern: `${BASE}/formula/parse`,
    handler: () =>
      json({
        ok: true,
        identifiers: ["price", "streak_days", "price_threshold"],
        unknown_identifiers: [],
        warnings: [],
        errors: [],
      }),
  },
  {
    method: "POST",
    pattern: `${BASE}/formula/test`,
    handler: () =>
      json({
        value: true,
        resolved_values: { price: 82.4, streak_days: 4, price_threshold: 80 },
        errors: [],
        warnings: [],
      }),
  },
  {
    method: "POST",
    pattern: `${BASE}/ruleset/preview`,
    handler: () =>
      json({
        status: "green",
        matched_rule_index: 3,
        label: "Below duration threshold",
        resolved_values: { price: 82.4, streak_days: 4 },
        derived_scalars: { ma_20: 79.8 },
        warnings: [],
      }),
  },
]);
