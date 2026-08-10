// Morning Briefing demo fixtures. Powers the department page (hero + feed +
// cabinet + schedules), the streaming "generating cockpit" for one run, and
// the Home snapshot card.
//
// Shape notes (matched against src/api/morning-briefing.ts + the page/hook):
//  - listMbRuns() (no status filter) backs the page feed; the page groups by
//    created_at into Today / This week / Older. listMbRuns("completed") backs
//    the Home snapshot card, which reads the latest by created_at.
//  - Every run is FINISHED (status "completed") with a `highlights` cover so
//    MbBigCard / MbReportRow / the Home card all render chips + rating + lede.
//  - The generating cockpit does NOT auto-play on mount. The page only starts
//    a live stream when the user clicks Run Now -> Generate (which POSTs
//    /runs/start and hands the returned report_id to useMbRunStream). We return
//    a FIXED report_id from /runs/start and register that run's /events SSE
//    script; the same id is also present in the runs list as a completed run,
//    so when the stream ends the page's refresh finds it finished and swaps the
//    cockpit for the finished MbBigCard.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, daysAgo } from "../clock";
import { registerStream } from "../DemoEventSource";
import { companyName, WATCHLIST_US } from "./persona";

import type {
  MbCardHighlights,
  MbChartRow,
  MbCoverMetric,
  MbCoverSpec,
  MbInstructions,
  MbRunDetail,
  MbRunStatus,
  MbRunSummary,
  MbSchedule,
  MbSectionRow,
  MbTemplate,
} from "../../api/morning-briefing";

const BASE = "/api/departments/morning-briefing";

// The report_id both returned from /runs/start and streamed via /events. It is
// also present in the runs list (as completed) so the page settles onto the
// finished card once the cockpit stream lands run.completed.
const LIVE_REPORT_ID = "mb-demo-live-0807";

// ---------------------------------------------------------------------------
// Cover / highlights builders
// ---------------------------------------------------------------------------

function metric(
  label: string,
  value: string,
  change: string | null,
  tone: string | null,
): MbCoverMetric {
  return { label, value, change, tone };
}

function highlights(
  subtitle: string,
  rating: string | null,
  metrics: MbCoverMetric[],
): MbCardHighlights {
  return { subtitle, rating, metrics };
}

// ---------------------------------------------------------------------------
// Report bodies (full detail rendered by MbBigCard -> MBReportRenderer)
// ---------------------------------------------------------------------------

function section(
  id: string,
  index: number,
  title: string,
  markdown: string,
): MbSectionRow {
  return { section_id: id, section_index: index, title, markdown, version: 1 };
}

function barChart(
  id: string,
  title: string,
  points: Array<{ label: string; value: number }>,
): MbChartRow {
  return {
    chart_id: id,
    chart_type: "bar",
    title,
    spec: {
      axes: { x: "Ticker", y: "Day change %" },
      data: points,
      source_ids: ["src_mkt"],
    },
    rendered_url: null,
    version: 1,
  };
}

const WATCH_NAMES = WATCHLIST_US.slice(0, 4)
  .map((s) => `${companyName(s)} (${s})`)
  .join(", ");

// A reusable finished briefing body. Sections reference a chart via the
// {{chart:...}} marker the adapter splits on.
function briefingDetail(
  run: MbRunSummary,
  cover: MbCoverSpec,
  moves: Array<{ label: string; value: number }>,
): MbRunDetail {
  return {
    report: run,
    error_message: null,
    cover,
    sections: [
      section(
        "sec_overnight",
        0,
        "Overnight & Pre-Market",
        "US index futures firmed overnight as rate-cut odds steadied and " +
          "volatility drifted lower. Asia closed mixed; Europe opened flat " +
          "into the US session. Breadth improved beneath the surface, with " +
          "cyclicals and semiconductors leading the early bid.[^src_mkt]",
      ),
      section(
        "sec_watchlist",
        1,
        "Watchlist Movers",
        `Watchlist names in focus: ${WATCH_NAMES}. Semiconductors set the ` +
          "tone again, while large-cap software traded quietly ahead of the " +
          "open.\n\n{{chart:chart_moves}}\n\nMoves shown are illustrative " +
          "sample figures for this demonstration only.",
      ),
      section(
        "sec_macro",
        2,
        "Macro & Rates",
        "The 10-year yield eased and the dollar softened modestly. Front-end " +
          "pricing continues to lean toward gradual easing later this year. " +
          "No tier-one data prints before the open; focus stays on positioning " +
          "into the afternoon.[^src_macro]",
      ),
      section(
        "sec_calendar",
        3,
        "On the Calendar",
        "Watch for after-hours earnings from two watchlist constituents and a " +
          "mid-morning Fed speaker. Nothing on the docket is expected to move " +
          "the broad tape before lunch.",
      ),
    ],
    charts: [barChart("chart_moves", "Watchlist pre-market moves (%)", moves)],
    citations: [
      {
        source_id: "src_mkt",
        tool_name: "market_data",
        display_index: 1,
        provenance: { title: "Illustrative market data snapshot" },
      },
      {
        source_id: "src_macro",
        tool_name: "web_search",
        display_index: 2,
        provenance: {
          title: "Illustrative macro wrap",
          url: "https://example.com/demo/macro-wrap",
        },
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// The finished runs. Newest first is not required (page + card sort), but we
// author them newest-first for readability. `daysAgo(0)` lands "today" in the
// frozen demo clock so the latest one becomes the hero + Home snapshot.
// ---------------------------------------------------------------------------

interface Briefing {
  run: MbRunSummary;
  detail: MbRunDetail;
}

function makeBriefing(opts: {
  id: string;
  subject: string;
  createdAt: string;
  completedAt: string;
  subtitle: string;
  rating: string;
  metrics: MbCoverMetric[];
  tldr: string[];
  moves: Array<{ label: string; value: number }>;
}): Briefing {
  const run: MbRunSummary = {
    report_id: opts.id,
    subject: opts.subject,
    trigger_kind: "schedule",
    schedule_id: "sch-premarket",
    template_id: "tpl-market-open",
    instructions_id: "ins-house-desk",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: opts.createdAt,
    completed_at: opts.completedAt,
    reasoning_effort: "medium",
    highlights: highlights(opts.subtitle, opts.rating, opts.metrics),
  };
  const cover: MbCoverSpec = {
    subtitle: opts.subtitle,
    tagline: "Pre-market desk read",
    tldr: opts.tldr,
    key_metrics: opts.metrics,
    rating: opts.rating,
    upside_pct: null,
  };
  return { run, detail: briefingDetail(run, cover, opts.moves) };
}

// The latest completed briefing — "today" in the frozen clock. Also the one
// the Home snapshot card surfaces.
const LATEST = makeBriefing({
  id: "mb-demo-0807",
  subject: "Morning Briefing - Thu 07 Aug",
  createdAt: daysAgo(0),
  completedAt: daysAgo(0),
  subtitle:
    "Futures firm into the open as rate-cut odds steady and volatility fades; " +
    "semis lead, software quiet.",
  rating: "Risk-on tilt",
  metrics: [
    metric("S&P 500 fut", "6,232", "+0.4%", "positive"),
    metric("US 10Y", "4.16%", "-2bp", "positive"),
    metric("VIX", "14.3", "-3.1%", "positive"),
    metric("Watchlist", "5 up / 1 dn", "leaders: semis", "neutral"),
  ],
  tldr: [
    "Index futures firm; breadth improving beneath the surface.",
    "Rates ease modestly; front-end still leans toward gradual cuts.",
    "Semiconductors lead the watchlist; software trades quietly.",
  ],
  moves: [
    { label: "NVDA", value: 1.9 },
    { label: "AMD", value: 1.4 },
    { label: "AVGO", value: 0.9 },
    { label: "AAPL", value: 0.4 },
  ],
});

const BRIEFINGS: Briefing[] = [
  LATEST,
  makeBriefing({
    id: "mb-demo-0806",
    subject: "Morning Briefing - Wed 06 Aug",
    createdAt: daysAgo(1),
    completedAt: daysAgo(1),
    subtitle:
      "A quieter tape after Tuesday's rally; futures flat as the desk waits " +
      "on afternoon supply and a Fed speaker.",
    rating: "Neutral",
    metrics: [
      metric("S&P 500 fut", "6,208", "+0.1%", "neutral"),
      metric("US 10Y", "4.18%", "flat", "neutral"),
      metric("VIX", "14.8", "-1.0%", "positive"),
    ],
    tldr: [
      "Futures flat into the open; consolidation after the rally.",
      "Yields steady; supply and a Fed speaker on the afternoon docket.",
    ],
    moves: [
      { label: "NVDA", value: 0.6 },
      { label: "AMD", value: -0.3 },
      { label: "AVGO", value: 0.2 },
      { label: "META", value: 0.5 },
    ],
  }),
  makeBriefing({
    id: "mb-demo-0805",
    subject: "Morning Briefing - Tue 05 Aug",
    createdAt: daysAgo(2),
    completedAt: daysAgo(2),
    subtitle:
      "Risk appetite returns as cooler inflation expectations lift futures; " +
      "megacaps broadly higher pre-market.",
    rating: "Risk-on tilt",
    metrics: [
      metric("S&P 500 fut", "6,201", "+0.7%", "positive"),
      metric("US 10Y", "4.20%", "-4bp", "positive"),
      metric("Watchlist", "6 up / 0 dn", "broad", "positive"),
    ],
    tldr: [
      "Broad pre-market bid; every watchlist name higher.",
      "Cooler inflation expectations support duration and equities.",
    ],
    moves: [
      { label: "NVDA", value: 2.3 },
      { label: "AMD", value: 1.8 },
      { label: "AVGO", value: 1.1 },
      { label: "AAPL", value: 0.9 },
    ],
  }),
  makeBriefing({
    id: "mb-demo-0801",
    subject: "Morning Briefing - Fri 01 Aug",
    createdAt: daysAgo(6),
    completedAt: daysAgo(6),
    subtitle:
      "Month-end positioning drives a soft open; defensives outperform as " +
      "the desk trims risk into the weekend.",
    rating: "Cautious",
    metrics: [
      metric("S&P 500 fut", "6,150", "-0.5%", "negative"),
      metric("US 10Y", "4.24%", "+3bp", "negative"),
      metric("VIX", "16.2", "+6.4%", "negative"),
    ],
    tldr: [
      "Soft open on month-end rebalancing; defensives lead.",
      "Yields tick up; the desk trims risk into the weekend.",
    ],
    moves: [
      { label: "NVDA", value: -0.8 },
      { label: "AMD", value: -1.2 },
      { label: "AVGO", value: -0.4 },
      { label: "AAPL", value: -0.2 },
    ],
  }),
  makeBriefing({
    id: "mb-demo-0730",
    subject: "Morning Briefing - Wed 30 Jul",
    createdAt: daysAgo(8),
    completedAt: daysAgo(8),
    subtitle:
      "Steady-as-she-goes ahead of the FOMC decision; futures little changed " +
      "as the market waits for guidance.",
    rating: "Neutral",
    metrics: [
      metric("S&P 500 fut", "6,120", "flat", "neutral"),
      metric("US 10Y", "4.22%", "flat", "neutral"),
      metric("Watchlist", "3 up / 3 dn", "mixed", "neutral"),
    ],
    tldr: [
      "Futures unchanged into an FOMC decision day.",
      "Watchlist mixed; the desk stays patient pre-announcement.",
    ],
    moves: [
      { label: "NVDA", value: 0.3 },
      { label: "AMD", value: -0.5 },
      { label: "AVGO", value: 0.4 },
      { label: "META", value: -0.2 },
    ],
  }),
];

// The finished form of the live run, revealed once the cockpit stream ends and
// the page refreshes the runs list. Authored "today" so it sits in the feed's
// Today group alongside LATEST.
const LIVE_FINISHED = makeBriefing({
  id: LIVE_REPORT_ID,
  subject: "Morning Briefing - Thu 07 Aug (Ad-hoc)",
  createdAt: DEMO_NOW_ISO,
  completedAt: DEMO_NOW_ISO,
  subtitle:
    "Ad-hoc desk read: futures hold their overnight gains; leadership stays " +
    "with semiconductors into the cash open.",
  rating: "Risk-on tilt",
  metrics: [
    metric("S&P 500 fut", "6,236", "+0.5%", "positive"),
    metric("US 10Y", "4.15%", "-3bp", "positive"),
    metric("VIX", "14.1", "-2.0%", "positive"),
  ],
  tldr: [
    "Futures hold overnight gains into the cash open.",
    "Semiconductors keep the leadership; software steady.",
  ],
  moves: [
    { label: "NVDA", value: 2.1 },
    { label: "AMD", value: 1.6 },
    { label: "AVGO", value: 1.0 },
    { label: "AAPL", value: 0.5 },
  ],
});
// Mark the live run as ad-hoc so it reads as a Run Now result.
LIVE_FINISHED.run.trigger_kind = "adhoc";
LIVE_FINISHED.run.schedule_id = null;

const ALL_BRIEFINGS: Briefing[] = [...BRIEFINGS, LIVE_FINISHED];

const RUN_BY_ID = new Map<string, Briefing>(
  ALL_BRIEFINGS.map((b) => [b.run.report_id, b]),
);

// ---------------------------------------------------------------------------
// Templates, instructions, schedules
// ---------------------------------------------------------------------------

const TEMPLATES: MbTemplate[] = [
  {
    id: "tpl-market-open",
    name: "Market Open Briefing",
    is_builtin: true,
    created_at: daysAgo(120),
    updated_at: daysAgo(30),
  },
  {
    id: "tpl-desk-note",
    name: "Desk Note (compact)",
    is_builtin: false,
    created_at: daysAgo(45),
    updated_at: daysAgo(12),
  },
];

const INSTRUCTIONS: MbInstructions[] = [
  {
    id: "ins-house-desk",
    name: "House Desk Voice",
    is_builtin: true,
    created_at: daysAgo(120),
    updated_at: daysAgo(60),
  },
  {
    id: "ins-macro-lean",
    name: "Macro-Leaning Profile",
    is_builtin: false,
    created_at: daysAgo(40),
    updated_at: daysAgo(9),
  },
];

const SCHEDULES: MbSchedule[] = [
  {
    id: "sch-premarket",
    time: "07:00",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "Pre-market briefing",
    is_enabled: true,
    template_id: "tpl-market-open",
    instructions_id: "ins-house-desk",
    enabled_connectors: { provider_ids: ["eodhd"], web_search: true },
    provider_kind: "openai",
    model: "gpt-5.4",
    language: "en",
    length: "normal",
    reasoning_effort: "medium",
    web_search: true,
  },
  {
    id: "sch-postclose",
    time: "16:30",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "Post-close wrap",
    is_enabled: false,
    template_id: "tpl-desk-note",
    instructions_id: "ins-macro-lean",
    enabled_connectors: { provider_ids: ["eodhd"], web_search: true },
    provider_kind: "openai",
    model: "gpt-5.4",
    language: "en",
    length: "concise",
    reasoning_effort: null,
    web_search: true,
  },
];

// ---------------------------------------------------------------------------
// REST routes
// ---------------------------------------------------------------------------

function listRuns(statusParam: string | null): MbRunSummary[] {
  const runs = ALL_BRIEFINGS.map((b) => b.run);
  if (!statusParam) return runs;
  return runs.filter((r) => r.status === (statusParam as MbRunStatus));
}

register([
  // List runs (feed + Home card). ?status=completed filters.
  {
    method: "GET",
    pattern: `${BASE}/runs`,
    handler: (req) => json(listRuns(req.url.searchParams.get("status"))),
  },

  // Run detail (full report for MbBigCard -> MBReportRenderer).
  {
    method: "GET",
    pattern: `${BASE}/runs/:id`,
    handler: (req) => {
      const b = RUN_BY_ID.get(req.params.id);
      return b ? json(b.detail) : notFound();
    },
  },

  // Start an ad-hoc run (Run Now -> Generate). Read-only: return the fixed
  // live report id whose /events SSE script drives the cockpit.
  {
    method: "POST",
    pattern: `${BASE}/runs/start`,
    handler: () => json({ report_id: LIVE_REPORT_ID }),
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

  // Templates.
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
        id: "tpl-demo-new",
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

  // Instructions.
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
        id: "ins-demo-new",
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

  // Schedules (read-only; edits return benign success).
  {
    method: "GET",
    pattern: `${BASE}/schedules`,
    handler: () => json(SCHEDULES),
  },
  {
    method: "POST",
    pattern: `${BASE}/schedules`,
    handler: () => json(SCHEDULES[0]),
  },
  {
    method: "PATCH",
    pattern: `${BASE}/schedules/:id`,
    handler: (req) =>
      json(SCHEDULES.find((s) => s.id === req.params.id) ?? SCHEDULES[0]),
  },
  {
    method: "DELETE",
    pattern: `${BASE}/schedules/:id`,
    handler: () => json(null, 204),
  },

  // Data sources (Run Now / schedule editor read these; keep it simple).
  {
    method: "GET",
    pattern: `${BASE}/data-sources`,
    handler: () =>
      json({
        sources: [
          {
            key: "eodhd",
            display_name: "Market Data (EODHD)",
            category: "financial",
            routing: "connector",
            available: true,
            enabled: true,
            unavailable_reason: null,
          },
          {
            key: "web_search",
            display_name: "Web Search",
            category: "web",
            routing: "native",
            available: true,
            enabled: true,
            unavailable_reason: null,
          },
        ],
      }),
  },
]);

// ---------------------------------------------------------------------------
// SSE cockpit script for the live run. Matches useMbRunStream's 9 event names
// and payload shapes. Runs on CLICK (Run Now -> Generate), not on mount.
// ---------------------------------------------------------------------------

const LIVE_SUBJECT = LIVE_FINISHED.run.subject;

const MB_STREAM_FRAMES = [
  {
    event: "run.started",
    data: { report_id: LIVE_REPORT_ID, subject: LIVE_SUBJECT },
    delayMs: 350,
  },
  // Research phase: market data + news tool calls.
  {
    event: "tool.called",
    data: {
      tool_name: "market_data",
      call_id: "call_mkt",
      args_summary: { query: "US index futures, watchlist pre-market" },
    },
    delayMs: 500,
  },
  {
    event: "tool.completed",
    data: { tool_name: "market_data", call_id: "call_mkt", ok: true },
    delayMs: 600,
  },
  {
    event: "tool.called",
    data: {
      tool_name: "web_search",
      call_id: "call_news",
      args_summary: { query: "overnight macro headlines, rates" },
    },
    delayMs: 450,
  },
  {
    event: "tool.completed",
    data: { tool_name: "web_search", call_id: "call_news", ok: true },
    delayMs: 650,
  },
  // Write phase: several sections.
  {
    event: "tool.called",
    data: { tool_name: "write_section", call_id: "call_s1" },
    delayMs: 400,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_overnight",
      section_index: 0,
      title: "Overnight & Pre-Market",
      version: 1,
    },
    delayMs: 550,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_watchlist",
      section_index: 1,
      title: "Watchlist Movers",
      version: 1,
    },
    delayMs: 550,
  },
  {
    event: "chart.emitted",
    data: {
      chart_id: "chart_moves",
      chart_type: "bar",
      title: "Watchlist pre-market moves (%)",
      version: 1,
    },
    delayMs: 500,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_macro",
      section_index: 2,
      title: "Macro & Rates",
      version: 1,
    },
    delayMs: 500,
  },
  {
    event: "section.written",
    data: {
      section_id: "sec_calendar",
      section_index: 3,
      title: "On the Calendar",
      version: 1,
    },
    delayMs: 500,
  },
  // Finalize.
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
      message: "Briefing ready.",
    },
    delayMs: 500,
  },
];

registerStream((url) =>
  url.pathname === `${BASE}/runs/${LIVE_REPORT_ID}/events`
    ? MB_STREAM_FRAMES
    : null,
);
