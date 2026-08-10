// Earnings Update (v2) demo fixtures. Powers the department page
// (hero + watchlist coverage drawer + Today/Up-next/Earlier feed + calendar +
// cabinet), the read-only schedule, the report settings modal (templates /
// instructions / data-sources), and the streaming "generating cockpit" for one
// on-demand run.
//
// Shape notes (matched against src/api/earnings-update.ts + the page/hooks/
// components + the euV2DetailAdapter):
//  - fetchRuns() (GET /runs, optional ?status=) backs the page feed and the
//    cabinet; the page groups by created_at into Today / Earlier this week.
//  - Every finished run is status "completed" with a `highlights` cover so
//    EuBigCard / EuReportRow render chips + rating + subtitle.
//  - getRun() (GET /runs/:id) returns the full RunDetail (8 EU sections +
//    charts + citations + cover). EUV2ReportRenderer -> adaptEuV2DetailToSchema
//    consumes it: section markdown carries `[^src_id]` citation markers and
//    `{{chart:id}}` chart placeholders; cover.tone drives metric chip tone.
//  - The generating cockpit does NOT auto-play on mount. The page's `live`
//    state is set ONLY by OnDemandReportModal.onStarted (user clicks
//    "Generate report" -> POST /runs/start). We return a FIXED report_id from
//    /runs/start and register that run's /events SSE script (runEventsUrl ->
//    /runs/:id/events). The same id is present in the runs list as a completed
//    run, so when the stream lands run.completed the page's refresh finds it
//    finished and swaps the cockpit for the finished EuBigCard.
//  - Watchlist entries use WatchlistEntry (id/ticker/company_name/created_at);
//    "next earnings date" is surfaced via the schedule join (useEuSchedule
//    byTicker), not a field on the entry itself.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, hoursAgo, daysAgo } from "../clock";
import { registerStream } from "../DemoEventSource";
import { companyName } from "./persona";

import type {
  CardHighlights,
  ChartRow,
  CoverMetric,
  CoverSpec,
  DataSource,
  EuInstructionsSummary,
  EuScheduleEntry,
  EuSettings,
  EuTemplate,
  RunDetail,
  RunStatus,
  RunSummary,
  SectionRow,
  WatchlistEntry,
} from "../../api/earnings-update";

const BASE = "/api/departments/earnings-update/v2";

// The report_id both returned from /runs/start and streamed via /events. Also
// present in the runs list (as completed) so the page settles onto the finished
// EuBigCard once the cockpit stream lands run.completed.
const LIVE_REPORT_ID = "eu-demo-live-nvda-0807";

// ---------------------------------------------------------------------------
// Cover / highlights / section builders
// ---------------------------------------------------------------------------

function metric(
  label: string,
  value: string,
  change: string | null,
  tone: string | null,
): CoverMetric {
  return { label, value, change, tone };
}

function highlights(
  subtitle: string,
  rating: string | null,
  metrics: CoverMetric[],
): CardHighlights {
  return { subtitle, rating, metrics };
}

function section(
  id: string,
  index: number,
  title: string,
  markdown: string,
): SectionRow {
  return { section_id: id, section_index: index, title, markdown, version: 1 };
}

function barChart(
  id: string,
  title: string,
  yLabel: string,
  points: Array<{ label: string; value: number }>,
): ChartRow {
  return {
    chart_id: id,
    chart_type: "bar",
    title,
    spec: {
      axes: { x: "Segment", y: yLabel },
      data: points,
      source_ids: ["src_financials"],
    },
    rendered_url: null,
    version: 1,
  };
}

// ---------------------------------------------------------------------------
// A finished earnings note body: the 8 EU sections. The revenue chart is
// referenced inline from Key Financials via the {{chart:...}} marker the
// adapter splits on; citation markers ([^src_...]) resolve to display indices.
// ---------------------------------------------------------------------------

interface NoteOpts {
  id: string;
  ticker: string;
  fiscalDate: string; // e.g. "2026-Q2"
  quarterLabel: string; // e.g. "Q2 FY2026"
  createdAt: string;
  completedAt: string;
  triggerKind: "scheduled" | "on_demand";
  reactionPct: number; // after-hours move, %
  epsActual: string;
  epsEst: string;
  epsBeat: string; // e.g. "+6.1%"
  revActual: string;
  revEst: string;
  revYoY: string; // e.g. "+41% YoY"
  subtitle: string;
  rating: string;
  guidance: string;
  segments: Array<{ label: string; value: number }>;
  segmentUnit: string; // chart y-axis label
}

interface Note {
  run: RunSummary;
  detail: RunDetail;
}

function makeNote(opts: NoteOpts): Note {
  const name = companyName(opts.ticker);
  const reactionTone = opts.reactionPct >= 0 ? "positive" : "negative";
  const reactionStr = `${opts.reactionPct >= 0 ? "+" : ""}${opts.reactionPct.toFixed(1)}%`;

  const metrics: CoverMetric[] = [
    metric("EPS", opts.epsActual, opts.epsBeat, "positive"),
    metric("Revenue", opts.revActual, opts.revYoY, "positive"),
    metric("After-hours", reactionStr, "vs. prior close", reactionTone),
    metric("Consensus", "Beat", "top & bottom line", "positive"),
  ];

  const subject = `${name} (${opts.ticker}) — ${opts.quarterLabel} Earnings Update`;

  const run: RunSummary = {
    report_id: opts.id,
    ticker: opts.ticker,
    subject,
    template_id: "eu_default",
    trigger_kind: opts.triggerKind,
    fiscal_date: opts.fiscalDate,
    language: "en",
    length: "normal",
    status: "completed",
    created_at: opts.createdAt,
    completed_at: opts.completedAt,
    reasoning_effort: "medium",
    highlights: highlights(opts.subtitle, opts.rating, metrics),
  };

  const cover: CoverSpec = {
    subtitle: opts.subtitle,
    tagline: `${opts.quarterLabel} print`,
    tldr: [
      `EPS ${opts.epsActual} vs. ${opts.epsEst} est. (${opts.epsBeat}); revenue ${opts.revActual} (${opts.revYoY}).`,
      `Shares moved ${reactionStr} after hours as the desk digested the print.`,
      `Guidance: ${opts.guidance}`,
    ],
    key_metrics: metrics,
    rating: opts.rating,
    upside_pct: null,
  };

  const detail: RunDetail = {
    report: run,
    error_message: null,
    cover,
    sections: [
      section(
        "sec_quick_take",
        0,
        "Quick Take",
        `${name} delivered a ${opts.quarterLabel} that came in ahead of ` +
          `consensus on both the top and bottom line. EPS of ${opts.epsActual} ` +
          `beat the ${opts.epsEst} estimate (${opts.epsBeat}), and revenue of ` +
          `${opts.revActual} grew ${opts.revYoY}.[^src_filing] Shares traded ` +
          `${reactionStr} in the after-hours session. This is an illustrative ` +
          `demonstration note and not investment advice.`,
      ),
      section(
        "sec_market_reaction",
        1,
        "Market Reaction",
        `The stock reacted ${reactionStr} versus the prior close in extended ` +
          `trading, with volume running well above the trailing average as the ` +
          `print crossed the wire.[^src_filing] Options-implied move into the ` +
          `event had been in the high-single-digit range, so the realized move ` +
          `sat roughly in line with what the market had priced.`,
      ),
      section(
        "sec_key_financials",
        2,
        "Key Financials",
        `Revenue of ${opts.revActual} (${opts.revYoY}) and EPS of ` +
          `${opts.epsActual} (${opts.epsBeat} vs. est.) both cleared the bar. ` +
          `Gross margin held firm and operating leverage improved as the top ` +
          `line outgrew operating expenses.[^src_financials]\n\n` +
          `{{chart:chart_segments}}\n\n` +
          `Segment figures above are illustrative sample data for this ` +
          `demonstration only.`,
      ),
      section(
        "sec_operational",
        3,
        "Operational Highlights",
        `Management pointed to broad-based demand and a healthy backlog. ` +
          `Unit economics were stable, and the company continued to invest in ` +
          `capacity to meet forward demand.[^src_transcript] Cash generation ` +
          `remained strong, supporting the balance sheet and the buyback ` +
          `program.`,
      ),
      section(
        "sec_guidance",
        4,
        "Forward Guidance",
        `For the next quarter, ${name} guided ${opts.guidance} The outlook ` +
          `landed at or above the Street's prior forecast, which the market ` +
          `read as a constructive signal on near-term momentum.[^src_transcript]`,
      ),
      section(
        "sec_earnings_call",
        5,
        "Earnings Call",
        `On the call, management fielded questions on demand durability, ` +
          `pricing, and the margin trajectory into next year. The tone was ` +
          `confident; leadership reiterated the multi-year investment thesis ` +
          `and emphasized visibility into forward bookings.[^src_transcript]`,
      ),
      section(
        "sec_risk",
        6,
        "Risk Assessment",
        `Key watch items include competitive intensity, the pace of hyperscaler ` +
          `capex, and any deceleration in the core growth driver. Valuation ` +
          `leaves limited room for execution missteps, so forward quarters ` +
          `carry a higher bar. None of the above is a recommendation.`,
      ),
      section(
        "sec_thesis",
        7,
        "Thesis Check",
        `The print is consistent with the standing thesis: durable demand, ` +
          `expanding margins, and disciplined capital return. Nothing in this ` +
          `quarter argues for a change to the framing; the setup remains ` +
          `${opts.rating.toLowerCase()} on the illustrative demo book.`,
      ),
    ],
    charts: [
      barChart(
        "chart_segments",
        `${name} revenue by segment`,
        opts.segmentUnit,
        opts.segments,
      ),
    ],
    citations: [
      {
        source_id: "src_filing",
        tool_name: "earnings_filing",
        display_index: 1,
        provenance: {
          title: `${name} ${opts.quarterLabel} press release (illustrative)`,
          url: "https://example.com/demo/earnings/press-release",
        },
      },
      {
        source_id: "src_financials",
        tool_name: "financials",
        display_index: 2,
        provenance: { title: "Illustrative financial statements snapshot" },
      },
      {
        source_id: "src_transcript",
        tool_name: "earnings_transcript",
        display_index: 3,
        provenance: {
          title: `${name} ${opts.quarterLabel} earnings call transcript (illustrative)`,
          url: "https://example.com/demo/earnings/transcript",
        },
      },
    ],
  };

  return { run, detail };
}

// ---------------------------------------------------------------------------
// The finished notes. Authored newest-first for readability (the page + cards
// sort). daysAgo(0)/hoursAgo land "today"; older ones fall into the feed's
// Earlier-this-week group.
// ---------------------------------------------------------------------------

const NOTES: Note[] = [
  makeNote({
    id: "eu-demo-msft-0807",
    ticker: "MSFT",
    fiscalDate: "2026-Q4",
    quarterLabel: "Q4 FY2026",
    createdAt: hoursAgo(3),
    completedAt: hoursAgo(3),
    triggerKind: "scheduled",
    reactionPct: 4.2,
    epsActual: "$3.61",
    epsEst: "$3.42",
    epsBeat: "+5.6%",
    revActual: "$74.9B",
    revEst: "$72.1B",
    revYoY: "+18% YoY",
    subtitle:
      "Cloud reaccelerates and AI monetization lifts margins; the print beat " +
      "on both lines and guidance stepped up.",
    rating: "Constructive",
    guidance:
      "double-digit revenue growth with continued cloud strength and stable operating margins.",
    segments: [
      { label: "Intelligent Cloud", value: 32.1 },
      { label: "Productivity", value: 22.4 },
      { label: "More Personal Computing", value: 20.4 },
    ],
    segmentUnit: "Revenue ($B)",
  }),
  makeNote({
    id: "eu-demo-googl-0806",
    ticker: "GOOGL",
    fiscalDate: "2026-Q2",
    quarterLabel: "Q2 FY2026",
    createdAt: daysAgo(1),
    completedAt: daysAgo(1),
    triggerKind: "scheduled",
    reactionPct: 2.7,
    epsActual: "$2.34",
    epsEst: "$2.18",
    epsBeat: "+7.3%",
    revActual: "$96.4B",
    revEst: "$93.8B",
    revYoY: "+14% YoY",
    subtitle:
      "Search holds up and Cloud swings to healthier margins; ad demand steady " +
      "into the back half of the year.",
    rating: "Neutral-to-positive",
    guidance:
      "steady ad growth with ongoing Cloud margin expansion and disciplined capex.",
    segments: [
      { label: "Search & other", value: 52.3 },
      { label: "YouTube ads", value: 10.1 },
      { label: "Google Cloud", value: 14.7 },
      { label: "Other", value: 19.3 },
    ],
    segmentUnit: "Revenue ($B)",
  }),
  makeNote({
    id: "eu-demo-aapl-0805",
    ticker: "AAPL",
    fiscalDate: "2026-Q3",
    quarterLabel: "Q3 FY2026",
    createdAt: daysAgo(2),
    completedAt: daysAgo(2),
    triggerKind: "on_demand",
    reactionPct: -1.3,
    epsActual: "$1.58",
    epsEst: "$1.52",
    epsBeat: "+3.9%",
    revActual: "$91.2B",
    revEst: "$89.7B",
    revYoY: "+6% YoY",
    subtitle:
      "Services strength offsets a softer hardware quarter; the modest guide " +
      "left shares slightly lower after hours.",
    rating: "Neutral",
    guidance:
      "low-to-mid single-digit revenue growth with continued Services momentum.",
    segments: [
      { label: "iPhone", value: 45.8 },
      { label: "Services", value: 26.1 },
      { label: "Mac", value: 8.2 },
      { label: "Wearables & Home", value: 11.1 },
    ],
    segmentUnit: "Revenue ($B)",
  }),
  makeNote({
    id: "eu-demo-pltr-0804",
    ticker: "PLTR",
    fiscalDate: "2026-Q2",
    quarterLabel: "Q2 FY2026",
    createdAt: daysAgo(3),
    completedAt: daysAgo(3),
    triggerKind: "scheduled",
    reactionPct: 6.9,
    epsActual: "$0.19",
    epsEst: "$0.15",
    epsBeat: "+26.7%",
    revActual: "$1.02B",
    revEst: "$0.96B",
    revYoY: "+34% YoY",
    subtitle:
      "US commercial reaccelerates on AI platform demand; the beat-and-raise " +
      "sent shares sharply higher after hours.",
    rating: "Constructive",
    guidance:
      "another sequential step-up in US commercial revenue and expanding adjusted margins.",
    segments: [
      { label: "US commercial", value: 0.34 },
      { label: "US government", value: 0.42 },
      { label: "International", value: 0.26 },
    ],
    segmentUnit: "Revenue ($B)",
  }),
];

// The finished form of the LIVE run, revealed once the cockpit stream ends and
// the page refreshes the runs list. Authored "today" (DEMO_NOW) so it sits in
// the feed's Today group; on_demand trigger so it reads as a Run-Now result.
const LIVE_FINISHED = makeNote({
  id: LIVE_REPORT_ID,
  ticker: "NVDA",
  fiscalDate: "2026-Q2",
  quarterLabel: "Q2 FY2026",
  createdAt: DEMO_NOW_ISO,
  completedAt: DEMO_NOW_ISO,
  triggerKind: "on_demand",
  reactionPct: 5.4,
  epsActual: "$1.24",
  epsEst: "$1.17",
  epsBeat: "+6.0%",
  revActual: "$46.8B",
  revEst: "$44.1B",
  revYoY: "+41% YoY",
  subtitle:
    "Data-center demand stays red-hot and margins hold near peak; the beat-and-raise " +
    "lifted shares in extended trading.",
  rating: "Constructive",
  guidance:
    "another sequential revenue step-up led by data center, with gross margin in the low-to-mid 70s.",
  segments: [
    { label: "Data Center", value: 40.1 },
    { label: "Gaming", value: 3.4 },
    { label: "Professional Viz", value: 1.6 },
    { label: "Automotive", value: 1.7 },
  ],
  segmentUnit: "Revenue ($B)",
});

const ALL_NOTES: Note[] = [...NOTES, LIVE_FINISHED];

const RUN_BY_ID = new Map<string, Note>(
  ALL_NOTES.map((n) => [n.run.report_id, n]),
);

// ---------------------------------------------------------------------------
// Watchlist — 6 persona tickers. company_name from the persona helper.
// ---------------------------------------------------------------------------

const WATCH_TICKERS = ["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "PLTR"] as const;

const WATCHLIST: WatchlistEntry[] = WATCH_TICKERS.map((ticker, i) => ({
  id: `wl-${ticker.toLowerCase()}`,
  ticker,
  company_name: companyName(ticker),
  created_at: daysAgo(30 - i * 3),
}));

// ---------------------------------------------------------------------------
// Schedule — read-only. "Next earnings date" surfaces via the watchlist-card
// join (useEuSchedule.byTicker joins soonest pending release per ticker). Two
// upcoming pending releases plus a couple already-reported rows that link to
// finished notes.
// ---------------------------------------------------------------------------

const SCHEDULE: EuScheduleEntry[] = [
  {
    id: "sch-amzn-q2",
    ticker: "AMZN",
    fiscal_date: "2026-Q2",
    release_timing: "post_market",
    eps_estimate: "$1.28",
    revenue_estimate: "$162.4B",
    scheduled_run_at: hoursAgo(-6), // ~6h out from DEMO_NOW
    status: "pending",
    attempts: 0,
    report_id: null,
  },
  {
    id: "sch-nvda-q3",
    ticker: "NVDA",
    fiscal_date: "2026-Q3",
    release_timing: "post_market",
    eps_estimate: "$1.31",
    revenue_estimate: "$49.6B",
    scheduled_run_at: daysAgo(-2), // ~2 days out
    status: "pending",
    attempts: 0,
    report_id: null,
  },
  {
    id: "sch-msft-q4",
    ticker: "MSFT",
    fiscal_date: "2026-Q4",
    release_timing: "post_market",
    eps_estimate: "$3.42",
    revenue_estimate: "$72.1B",
    scheduled_run_at: hoursAgo(3),
    status: "reported",
    attempts: 1,
    report_id: "eu-demo-msft-0807",
  },
  {
    id: "sch-googl-q2",
    ticker: "GOOGL",
    fiscal_date: "2026-Q2",
    release_timing: "post_market",
    eps_estimate: "$2.18",
    revenue_estimate: "$93.8B",
    scheduled_run_at: daysAgo(1),
    status: "reported",
    attempts: 1,
    report_id: "eu-demo-googl-0806",
  },
];

// ---------------------------------------------------------------------------
// Settings, templates, instructions, data-sources.
// ---------------------------------------------------------------------------

const SETTINGS: EuSettings = {
  provider_kind: "openai",
  model: "gpt-5.4",
  template_id: "eu_default",
  language: "en",
  length: "normal",
  reasoning_effort: "medium",
  enabled_provider_ids: ["eodhd"],
  web_search_enabled: true,
  instructions_id: "eu-ins-house",
  batch_enabled: false,
};

const TEMPLATES: EuTemplate[] = [
  {
    id: "eu_default",
    name: "Standard Earnings Update",
    is_builtin: true,
    created_at: daysAgo(180),
    updated_at: daysAgo(40),
  },
  {
    id: "eu-tpl-quick",
    name: "Quick Reaction Note",
    is_builtin: false,
    created_at: daysAgo(60),
    updated_at: daysAgo(14),
  },
];

const INSTRUCTIONS: EuInstructionsSummary[] = [
  {
    id: "eu-ins-house",
    name: "House Earnings Voice",
    is_builtin: true,
    created_at: daysAgo(180),
    updated_at: daysAgo(50),
  },
  {
    id: "eu-ins-buyside",
    name: "Buy-Side Deep Dive",
    is_builtin: false,
    created_at: daysAgo(35),
    updated_at: daysAgo(8),
  },
];

const DATA_SOURCES: DataSource[] = [
  {
    key: "eodhd",
    display_name: "Fundamentals & Prices (EODHD)",
    category: "financial",
    routing: "curated",
    available: true,
    enabled: true,
    unavailable_reason: null,
  },
  {
    key: "eodhd_calendar",
    display_name: "Earnings Calendar (EODHD)",
    category: "financial",
    routing: "curated",
    available: true,
    enabled: true,
    unavailable_reason: null,
  },
  {
    key: "news",
    display_name: "Financial News",
    category: "news",
    routing: "dispatcher",
    available: true,
    enabled: true,
    unavailable_reason: null,
  },
  {
    key: "model_web_search",
    display_name: "Web Search (model-native)",
    category: "web_search",
    routing: "model_native",
    available: true,
    enabled: true,
    unavailable_reason: null,
  },
];

// ---------------------------------------------------------------------------
// REST routes
// ---------------------------------------------------------------------------

function listRuns(statusParam: string | null): RunSummary[] {
  const runs = ALL_NOTES.map((n) => n.run);
  if (!statusParam) return runs;
  return runs.filter((r) => r.status === (statusParam as RunStatus));
}

register([
  // ----- Watchlist -----
  {
    method: "GET",
    pattern: `${BASE}/watchlist`,
    handler: () => json({ entries: WATCHLIST }),
  },
  // Add (read-only): echo a benign new entry with the requested ticker.
  {
    method: "POST",
    pattern: `${BASE}/watchlist`,
    handler: (req) => {
      const body = (req.body ?? {}) as { ticker?: string };
      const ticker = (body.ticker ?? "TICK").toUpperCase();
      const entry: WatchlistEntry = {
        id: `wl-demo-${ticker.toLowerCase()}`,
        ticker,
        company_name: companyName(ticker),
        created_at: DEMO_NOW_ISO,
      };
      return json(entry);
    },
  },
  {
    method: "DELETE",
    pattern: `${BASE}/watchlist/:id`,
    handler: () => json(null, 204),
  },
  // Refresh earnings dates (EuRefreshButton) — benign success.
  {
    method: "POST",
    pattern: `${BASE}/watchlist/sync`,
    handler: () => json({ synced: WATCHLIST.length }),
  },

  // ----- Settings -----
  {
    method: "GET",
    pattern: `${BASE}/settings`,
    handler: () => json(SETTINGS),
  },
  {
    method: "PUT",
    pattern: `${BASE}/settings`,
    handler: (req) => json({ ...SETTINGS, ...((req.body ?? {}) as object) }),
  },

  // ----- Data sources (settings modal) -----
  {
    method: "GET",
    pattern: `${BASE}/data-sources`,
    handler: () => json({ sources: DATA_SOURCES }),
  },

  // ----- Templates -----
  {
    method: "GET",
    pattern: `${BASE}/templates`,
    handler: () => json({ templates: TEMPLATES }),
  },
  {
    method: "POST",
    pattern: `${BASE}/templates`,
    handler: () =>
      json({
        id: "eu-tpl-demo-new",
        name: "Uploaded (demo)",
        is_builtin: false,
        created_at: DEMO_NOW_ISO,
        updated_at: DEMO_NOW_ISO,
      }),
  },
  {
    method: "DELETE",
    pattern: `${BASE}/templates/:id`,
    handler: () => json(null, 204),
  },

  // ----- Instruction profiles -----
  {
    method: "GET",
    pattern: `${BASE}/instructions`,
    handler: () => json(INSTRUCTIONS),
  },
  {
    method: "POST",
    pattern: `${BASE}/instructions`,
    handler: () =>
      json({
        id: "eu-ins-demo-new",
        name: "Uploaded (demo)",
        is_builtin: false,
        created_at: DEMO_NOW_ISO,
        updated_at: DEMO_NOW_ISO,
      }),
  },
  {
    method: "DELETE",
    pattern: `${BASE}/instructions/:id`,
    handler: () => json(null, 204),
  },

  // ----- Schedule (read-only) -----
  {
    method: "GET",
    pattern: `${BASE}/schedule`,
    handler: () => json({ schedule: SCHEDULE }),
  },

  // ----- Runs -----
  // Start an on-demand run (OnDemandReportModal -> Generate). Read-only: return
  // the fixed live report id whose /events SSE script drives the cockpit.
  {
    method: "POST",
    pattern: `${BASE}/runs/start`,
    handler: () => json({ report_id: LIVE_REPORT_ID }),
  },
  // List runs (feed + cabinet). ?status= filters.
  {
    method: "GET",
    pattern: `${BASE}/runs`,
    handler: (req) => json(listRuns(req.url.searchParams.get("status"))),
  },
  // Run detail (full report for EUV2ReportRenderer -> adaptEuV2DetailToSchema).
  {
    method: "GET",
    pattern: `${BASE}/runs/:id`,
    handler: (req) => {
      const n = RUN_BY_ID.get(req.params.id);
      return n ? json(n.detail) : notFound();
    },
  },
  // Cancel / delete — benign success (read-only demo).
  {
    method: "POST",
    pattern: `${BASE}/runs/:id/cancel`,
    handler: () => json({ cancelled: true }),
  },
  {
    method: "DELETE",
    pattern: `${BASE}/runs/:id`,
    handler: () => json(null, 204),
  },
]);

// ---------------------------------------------------------------------------
// SSE cockpit script for the live NVDA run. Matches useEuRunStream's 9 event
// names and payload shapes. Runs on CLICK (Generate report), not on mount.
//
// Payload shapes (matched against useEuRunStream + EuGeneratingCard/euPhase):
//  - run.started      { report_id, subject }   (subject -> generating title)
//  - tool.called      { tool_name, call_id, args_summary? }
//                     args_summary is a dict; euPhase joins its scalar values.
//                     write_section/emit_chart map to the "write" phase;
//                     set_cover/finalize -> "finalize"; else -> "research".
//  - tool.completed   { tool_name, call_id, ok }
//  - section.written  { section_id, section_index, title, version }  (title ->
//                     monoCode; increments sectionsWritten)
//  - chart.emitted    { chart_id, chart_type, title, version }  (increments
//                     chartsEmitted)
//  - run.completed    { report_id, status, subject, message }  (terminal;
//                     `message` surfaces as terminalMessage; stream closes)
// ---------------------------------------------------------------------------

const LIVE_SUBJECT = LIVE_FINISHED.run.subject;

const EU_STREAM_FRAMES = [
  {
    event: "run.started",
    data: { report_id: LIVE_REPORT_ID, subject: LIVE_SUBJECT },
    delayMs: 350,
  },
  // Research phase: pull the filing, transcript, financials.
  {
    event: "tool.called",
    data: {
      tool_name: "earnings_filing",
      call_id: "call_filing",
      args_summary: { symbol: "NVDA", period: "Q2 FY2026" },
    },
    delayMs: 500,
  },
  {
    event: "tool.completed",
    data: { tool_name: "earnings_filing", call_id: "call_filing", ok: true },
    delayMs: 600,
  },
  {
    event: "tool.called",
    data: {
      tool_name: "earnings_transcript",
      call_id: "call_transcript",
      args_summary: { symbol: "NVDA", event: "Q2 FY2026 call" },
    },
    delayMs: 500,
  },
  {
    event: "tool.completed",
    data: {
      tool_name: "earnings_transcript",
      call_id: "call_transcript",
      ok: true,
    },
    delayMs: 650,
  },
  {
    event: "tool.called",
    data: {
      tool_name: "financials",
      call_id: "call_financials",
      args_summary: { symbol: "NVDA", statements: "income, balance, cash" },
    },
    delayMs: 450,
  },
  {
    event: "tool.completed",
    data: { tool_name: "financials", call_id: "call_financials", ok: true },
    delayMs: 600,
  },
  // Write phase: the 8 EU sections + the revenue chart.
  {
    event: "tool.called",
    data: { tool_name: "write_section", call_id: "call_w1" },
    delayMs: 400,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_quick_take",
      section_index: 0,
      title: "Quick Take",
      version: 1,
    },
    delayMs: 500,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_market_reaction",
      section_index: 1,
      title: "Market Reaction",
      version: 1,
    },
    delayMs: 450,
  },
  {
    event: "tool.called",
    data: { tool_name: "emit_chart", call_id: "call_chart" },
    delayMs: 400,
  },
  {
    event: "chart.emitted",
    data: {
      chart_id: "chart_segments",
      chart_type: "bar",
      title: "NVIDIA revenue by segment",
      version: 1,
    },
    delayMs: 500,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_key_financials",
      section_index: 2,
      title: "Key Financials",
      version: 1,
    },
    delayMs: 500,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_operational",
      section_index: 3,
      title: "Operational Highlights",
      version: 1,
    },
    delayMs: 450,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_guidance",
      section_index: 4,
      title: "Forward Guidance",
      version: 1,
    },
    delayMs: 450,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_earnings_call",
      section_index: 5,
      title: "Earnings Call",
      version: 1,
    },
    delayMs: 450,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_risk",
      section_index: 6,
      title: "Risk Assessment",
      version: 1,
    },
    delayMs: 450,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_thesis",
      section_index: 7,
      title: "Thesis Check",
      version: 1,
    },
    delayMs: 450,
  },
  // Finalize: set the cover.
  {
    event: "tool.called",
    data: { tool_name: "set_cover", call_id: "call_cover" },
    delayMs: 400,
  },
  {
    event: "run.completed",
    data: {
      report_id: LIVE_REPORT_ID,
      status: "completed",
      subject: LIVE_SUBJECT,
      message: "Earnings update ready.",
    },
    delayMs: 500,
  },
];

registerStream((url) =>
  url.pathname === `${BASE}/runs/${LIVE_REPORT_ID}/events`
    ? EU_STREAM_FRAMES
    : null,
);
