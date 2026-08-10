// Retail Sentiment demo fixtures. Powers the department dashboard
// (RsOverviewView) for each watchlist ticker: the hero (sentiment index,
// direction, bull/bear split, buzz), momentum gauge, narrative themes, active
// signals, the data-crosscheck tiles (aggregated sentiment + analyst gap), and
// the evidence list. Also serves the settings panel's schedule + config.
//
// Shape notes (matched against src/api/retail-sentiment.ts + RsOverviewView):
//  - getDashboard(ticker) -> GET /dashboard/:ticker returns a
//    DashboardResponse<RetailSentimentPayload>: { payload, generated_at,
//    is_stale, provenance }. On mount RsOverviewView GETs this and renders the
//    whole dashboard from `payload`. We serve a fully-populated, recently
//    generated (not stale) payload per watchlist ticker so the page never lands
//    on the empty state.
//  - getHistory(ticker) -> GET /dashboard/:ticker/history backs the 7-day trend
//    strips; returns an array of { payload, generated_at } snapshots.
//  - refreshDashboard(ticker) -> POST /dashboard/:ticker/refresh. Read-only demo:
//    the reading is already present, so we return { status: "completed" } which
//    cleanly stops the "Generating…" state without polling.
//  - getConfig / putConfig -> GET/PUT /config (view_config + threshold_overrides).
//  - getSchedule / putSchedule -> GET/PUT /schedule.
// Illustrative only — not investment advice.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, hoursAgo, daysAgo } from "../clock";
import { companyName, WATCHLIST_US } from "./persona";

import type {
  DashboardConfig,
  DashboardResponse,
  RefreshResult,
  RetailSentimentPayload,
  RsSchedule,
} from "../../api/retail-sentiment";

const BASE = "/api/departments/retail_sentiment";

// ---------------------------------------------------------------------------
// Per-ticker dashboard payloads
// ---------------------------------------------------------------------------

const CAPTURED_AT = hoursAgo(3);

const PAYLOADS: Record<string, RetailSentimentPayload> = {
  NVDA: {
    subject: `${companyName("NVDA")} (NVDA)`,
    sentiment_score: 0.58,
    direction: "bullish",
    momentum: 0.34,
    trend_label: "Rising — buzz and tone both firming into the print",
    buzz_level: "high",
    buzz_note:
      "Mention volume is running roughly 2.4x the trailing 30-day baseline, concentrated on r/wallstreetbets, r/NVDA_Stock and fintwit ahead of the data-center guide. Elevated but still constructive, not a blow-off.",
    bull_pct: 71.4,
    bear_pct: 22.1,
    narratives: [
      "Blackwell ramp is the dominant bull thesis — retail is fixated on GB200 rack shipments and hyperscaler capex guides holding through 2027.",
      "Sovereign-AI and enterprise inference demand framed as a durable second leg beyond the training build-out.",
      "Bear counter-narrative centers on gross-margin normalization and the China H20 export overhang, but it is a minority voice this week.",
    ],
    signals: [
      {
        name: "Buzz spike into earnings",
        severity: "caution",
        note: "Mention volume +138% week-over-week two sessions before the print — crowded positioning raises the bar for a clean beat.",
      },
      {
        name: "Bull/bear ratio at 3-month high",
        severity: "info",
        note: "Bullish tone share (71%) sits in the top decile of the trailing quarter; historically a mild mean-reversion headwind.",
      },
      {
        name: "Options chatter skewed to calls",
        severity: "info",
        note: "Weekly-expiry call mentions outnumber puts ~4:1 in scraped threads, consistent with a put/call read below 0.7.",
      },
    ],
    evidence: [
      {
        title: "Blackwell rack shipments ahead of plan, checks suggest — supplier lead-times extending",
        url: "https://example.com/nvda/blackwell-rack-checks",
        source: "SemiAnalysis (blog)",
        classification: "bullish",
        published_at: hoursAgo(9),
      },
      {
        title: "r/wallstreetbets megathread: NVDA earnings positioning, calls stacked at 180/200",
        url: "https://example.com/nvda/wsb-megathread",
        source: "Reddit · r/wallstreetbets",
        classification: "bullish",
        published_at: hoursAgo(5),
      },
      {
        title: "Analyst trims price target on gross-margin normalization, keeps Buy",
        url: "https://example.com/nvda/margin-note",
        source: "Fintwit thread",
        classification: "bearish",
        published_at: daysAgo(1),
      },
      {
        title: "China H20 export licensing still unresolved — data-center mix question lingers",
        url: "https://example.com/nvda/h20-export",
        source: "Reuters",
        classification: "neutral",
        published_at: daysAgo(2),
      },
      {
        title: "Retail flows: NVDA remains the most-bought single name on the retail broker leaderboard",
        url: "https://example.com/nvda/retail-flows",
        source: "Vanda Research (summary)",
        classification: "bullish",
        published_at: daysAgo(1),
      },
    ],
    narrative:
      "Retail sentiment on NVDA is decisively bullish heading into the data-center print, with tone (71% bullish) and buzz (roughly 2.4x baseline) both elevated. The conversation is anchored on the Blackwell ramp and sovereign-AI demand, and options chatter skews heavily toward calls. The main risk the crowd under-weights is gross-margin normalization and the unresolved China H20 overhang; combined with three-month-high bullish positioning, that leaves the setup vulnerable to a sell-the-news reaction on anything short of a clean beat-and-raise.",
    aggregated_sentiment: 0.61,
    analyst_gap: 0.18,
    captured_at: CAPTURED_AT,
  },

  AAPL: {
    subject: `${companyName("AAPL")} (AAPL)`,
    sentiment_score: 0.12,
    direction: "neutral",
    momentum: -0.08,
    trend_label: "Flat to softening — enthusiasm cooling post-launch",
    buzz_level: "elevated",
    buzz_note:
      "Mentions are up modestly (~1.3x baseline) around the iPhone cycle and the Apple Intelligence rollout, but the tone is mixed and the thread volume is well below the AI-hardware names.",
    bull_pct: 46.8,
    bear_pct: 38.5,
    narratives: [
      "iPhone 17 upgrade-cycle debate is unresolved — bulls cite Pro-mix strength, bears point to elongated replacement cycles.",
      "Apple Intelligence feature cadence seen as underwhelming versus expectations; Siri delays cited repeatedly.",
      "Services growth and buyback remain the steady bull anchor for longer-horizon retail holders.",
    ],
    signals: [
      {
        name: "Sentiment near neutral",
        severity: "info",
        note: "Bull and bear shares are within ~8 points of each other — no crowd conviction in either direction this week.",
      },
      {
        name: "Momentum rolling over",
        severity: "caution",
        note: "Tone momentum has ticked negative as post-launch enthusiasm fades; watch for follow-through into the next reading.",
      },
    ],
    evidence: [
      {
        title: "iPhone 17 Pro lead-times shorten in week two — demand read is muddled",
        url: "https://example.com/aapl/leadtimes",
        source: "Supply-chain tracker",
        classification: "bearish",
        published_at: daysAgo(1),
      },
      {
        title: "Apple Intelligence: Siri overhaul slips again, r/apple reacts",
        url: "https://example.com/aapl/siri-slip",
        source: "Reddit · r/apple",
        classification: "bearish",
        published_at: hoursAgo(14),
      },
      {
        title: "Services run-rate hits new high; buyback pace intact — the durable bull case",
        url: "https://example.com/aapl/services",
        source: "Fintwit thread",
        classification: "bullish",
        published_at: daysAgo(2),
      },
      {
        title: "Holiday-quarter build orders in line with expectations, checks say",
        url: "https://example.com/aapl/build-orders",
        source: "Bloomberg (summary)",
        classification: "neutral",
        published_at: daysAgo(3),
      },
    ],
    narrative:
      "Retail sentiment on AAPL is balanced to slightly positive but conviction is thin: bull (47%) and bear (39%) shares are close, and tone momentum has just turned negative as the post-launch buzz fades. The crowd is split between an unresolved iPhone 17 upgrade-cycle debate and disappointment over the pace of Apple Intelligence features, offset by the steady Services-plus-buyback anchor that longer-horizon holders keep returning to. Absent a clear catalyst, expect the reading to drift sideways.",
    aggregated_sentiment: 0.09,
    analyst_gap: -0.05,
    captured_at: CAPTURED_AT,
  },

  PLTR: {
    subject: `${companyName("PLTR")} (PLTR)`,
    sentiment_score: 0.44,
    direction: "bullish",
    momentum: 0.51,
    trend_label: "Accelerating — retail conviction building fast",
    buzz_level: "high",
    buzz_note:
      "One of the most-discussed names on retail forums this week, mentions running ~3.1x baseline. Highly retail-driven and momentum-heavy, which cuts both ways — durable enthusiasm but stretched, reflexive positioning.",
    bull_pct: 64.2,
    bear_pct: 28.9,
    narratives: [
      "AIP (Artificial Intelligence Platform) commercial bootcamp conversions are the core bull story — retail treats each new logo as a proof point.",
      "US commercial revenue acceleration seen as the multiple-justifier; government segment viewed as the stable base.",
      "Bear pushback is almost entirely valuation — 'priced for perfection' recurs, with dilution and stock-based comp flagged.",
    ],
    signals: [
      {
        name: "Momentum at cycle high",
        severity: "alert",
        note: "Tone momentum (+0.51) is the strongest in the watchlist — reflexive retail chases like this can reverse sharply on any wobble.",
      },
      {
        name: "Valuation is the entire bear case",
        severity: "caution",
        note: "Bearish mentions cluster on multiple, not fundamentals — a narrow, fragile objection that a soft tape could amplify quickly.",
      },
      {
        name: "Heavy retail concentration",
        severity: "info",
        note: "Discussion skews to momentum-driven retail channels; institutional counter-voice is thin in the scraped sources.",
      },
    ],
    evidence: [
      {
        title: "New AIP bootcamp wins surface on r/PLTR — commercial pipeline read stays strong",
        url: "https://example.com/pltr/aip-bootcamps",
        source: "Reddit · r/PLTR",
        classification: "bullish",
        published_at: hoursAgo(7),
      },
      {
        title: "US commercial revenue growth reaccelerates in the latest disclosure",
        url: "https://example.com/pltr/us-commercial",
        source: "Fintwit thread",
        classification: "bullish",
        published_at: daysAgo(1),
      },
      {
        title: "'Priced for perfection' — the recurring bear objection on valuation",
        url: "https://example.com/pltr/valuation-bear",
        source: "Seeking Alpha (summary)",
        classification: "bearish",
        published_at: daysAgo(2),
      },
      {
        title: "Stock-based comp and share-count creep flagged in retail dilution thread",
        url: "https://example.com/pltr/dilution",
        source: "Reddit · r/stocks",
        classification: "bearish",
        published_at: daysAgo(2),
      },
      {
        title: "Government segment renewals characterized as steady base by defense-desk note",
        url: "https://example.com/pltr/gov-renewals",
        source: "Fintwit thread",
        classification: "neutral",
        published_at: daysAgo(3),
      },
    ],
    narrative:
      "Retail sentiment on PLTR is strongly bullish and, notably, accelerating — momentum (+0.51) is the highest in the watchlist and mention volume is running about 3.1x baseline. The bull case is almost entirely commercial-AIP execution, with each new bootcamp win treated as a proof point, while the bear case is narrow and valuation-only ('priced for perfection'). That combination — durable enthusiasm on a reflexive, retail-heavy tape with a single fragile objection — makes PLTR the most sentiment-driven name here and the most exposed to a fast reversal if momentum stalls.",
    aggregated_sentiment: 0.47,
    analyst_gap: 0.29,
    captured_at: CAPTURED_AT,
  },
};

// Any watchlist ticker without a hand-authored payload still gets a plausible,
// neutral dashboard so the demo never lands on the empty state.
function fallbackPayload(ticker: string): RetailSentimentPayload {
  return {
    subject: `${companyName(ticker)} (${ticker})`,
    sentiment_score: 0.08,
    direction: "neutral",
    momentum: 0.02,
    trend_label: "Flat — no strong retail signal this week",
    buzz_level: "low",
    buzz_note:
      "Mention volume is near the trailing baseline with no notable catalyst driving the conversation.",
    bull_pct: 44.0,
    bear_pct: 40.0,
    narratives: [
      "Discussion is thin and topic-diffuse — no single thesis dominates the retail conversation.",
      "Bulls and bears are roughly balanced, with no fresh catalyst to break the tie.",
    ],
    signals: [
      {
        name: "Low buzz",
        severity: "info",
        note: "Mention volume near baseline — sentiment reading carries less weight until activity picks up.",
      },
    ],
    evidence: [
      {
        title: `Quiet week for ${ticker} — no standout retail thread`,
        url: "https://example.com/generic/quiet-week",
        source: "Web search",
        classification: "neutral",
        published_at: daysAgo(1),
      },
    ],
    narrative: `Retail sentiment on ${ticker} is neutral this week. Mention volume is near baseline, the bull/bear split is roughly even, and there is no dominant thesis or fresh catalyst in the scraped conversation. Treat the reading as low-conviction until buzz picks up.`,
    aggregated_sentiment: 0.05,
    analyst_gap: 0.0,
    captured_at: CAPTURED_AT,
  };
}

function payloadFor(ticker: string): RetailSentimentPayload {
  return PAYLOADS[ticker.toUpperCase()] ?? fallbackPayload(ticker.toUpperCase());
}

function dashboardFor(
  ticker: string,
): DashboardResponse<RetailSentimentPayload> {
  return {
    payload: payloadFor(ticker),
    generated_at: CAPTURED_AT,
    is_stale: false,
    provenance: "web_search + news + financial (aggregated)",
  };
}

// ---------------------------------------------------------------------------
// 7-day history (backs the trend strips)
// ---------------------------------------------------------------------------

// Walk each ticker's headline score back over the last 7 days so the trend
// reads consistently with its momentum sign.
function historyFor(
  ticker: string,
): Array<{ payload: RetailSentimentPayload; generated_at: string }> {
  const base = payloadFor(ticker);
  const momentum = base.momentum ?? 0;
  const days = 7;
  const out: Array<{ payload: RetailSentimentPayload; generated_at: string }> = [];
  for (let i = days; i >= 0; i -= 1) {
    // Older snapshots sit "below" the current score along the momentum slope,
    // with a little jitter so the strip is not a straight line.
    const drift = momentum * (i / days) * 0.6;
    const jitter = ((i % 3) - 1) * 0.03;
    const score = Math.max(-1, Math.min(1, base.sentiment_score - drift + jitter));
    const bull = Math.max(0, Math.min(100, base.bull_pct - drift * 40));
    out.push({
      generated_at: daysAgo(i),
      payload: {
        ...base,
        sentiment_score: Number(score.toFixed(3)),
        bull_pct: Number(bull.toFixed(1)),
        bear_pct: Number((100 - bull - 6).toFixed(1)),
        captured_at: daysAgo(i),
      },
    });
  }
  return out;
}

// ---------------------------------------------------------------------------
// Config + schedule
// ---------------------------------------------------------------------------

const CONFIG: DashboardConfig = {
  view_config: {
    default_ticker: WATCHLIST_US[0],
    watchlist: [...WATCHLIST_US],
    show_evidence: true,
    show_crosscheck: true,
  },
  threshold_overrides: {
    buzz_elevated: 1.5,
    buzz_high: 2.0,
    bull_alert_pct: 70,
  },
};

const SCHEDULE: RsSchedule = {
  id: "rs-sch-demo",
  time: "16:30",
  timezone: "America/New_York",
  days_of_week: ["mon", "tue", "wed", "thu", "fri"],
  label: "Post-close retail sentiment sweep",
  is_enabled: true,
};

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

register([
  {
    method: "GET",
    pattern: `${BASE}/dashboard/:ticker`,
    handler: (req) => {
      const ticker = req.params.ticker;
      if (!ticker) return notFound();
      return json(dashboardFor(ticker));
    },
  },
  {
    method: "GET",
    pattern: `${BASE}/dashboard/:ticker/history`,
    handler: (req) => {
      const ticker = req.params.ticker;
      if (!ticker) return notFound();
      return json(historyFor(ticker));
    },
  },
  // Refresh is read-only in the demo: the reading is already present, so report
  // it as completed. RsOverviewView then clears "Generating…" without polling.
  {
    method: "POST",
    pattern: `${BASE}/dashboard/:ticker/refresh`,
    handler: (): ReturnType<typeof json> => {
      const result: RefreshResult = { job_run_id: null, status: "completed" };
      return json(result);
    },
  },

  // Config.
  {
    method: "GET",
    pattern: `${BASE}/config`,
    handler: () => json(CONFIG),
  },
  {
    method: "PUT",
    pattern: `${BASE}/config`,
    handler: (req) => {
      const patch = (req.body ?? {}) as Partial<DashboardConfig>;
      return json({
        view_config: { ...CONFIG.view_config, ...(patch.view_config ?? {}) },
        threshold_overrides: {
          ...CONFIG.threshold_overrides,
          ...(patch.threshold_overrides ?? {}),
        },
      } satisfies DashboardConfig);
    },
  },

  // Schedule.
  {
    method: "GET",
    pattern: `${BASE}/schedule`,
    handler: () => json({ schedule: SCHEDULE }),
  },
  {
    method: "PUT",
    pattern: `${BASE}/schedule`,
    handler: (req) => {
      const patch = (req.body ?? {}) as Partial<RsSchedule>;
      return json({ ...SCHEDULE, ...patch } satisfies RsSchedule);
    },
  },
]);

// Keep the frozen-now import referenced (used for provenance parity / future
// snapshots) without altering behavior.
void DEMO_NOW_ISO;
