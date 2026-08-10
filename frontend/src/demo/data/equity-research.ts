// Demo fixtures for the Equity Research (v3) department.
//
// Serves the v3 REST surface (runs list, run/report detail, templates,
// instructions, start-run, cancel, delete) from static data, and scripts the
// SSE "cockpit" stream for one in-progress run so the generating experience
// replays live with no backend.
//
// Wire shapes are pinned to the real client + hook:
//   - REST types: src/api/equity-research-v3.ts (V3ReportSummary, V3ReportDetail,
//     V3SectionRow, V3ChartRow, V3CitationRow, V3CoverSpec, V3TemplateSummary,
//     V3InstructionsSummary, V3Revision).
//   - SSE events: src/components/equity-research-v3/useV3RunStream.ts + its test.
//     run.started {subject, model, template_id}; tool.called {turn, tool_name};
//     tool.completed {turn, tool_name, ok, source_id?}; section.written
//     {section_id, char_count}; chart.emitted {chart_id, chart_type, title};
//     run.completed {section_count, chart_count, citation_count, message}.
//
// The split-pane viewer renders a run through adaptV3DetailToSchema, so section
// markdown uses [^source_id] citation markers and {{chart:id}} inline chart
// placeholders, and each ChartRow.spec carries {data: [{label, value}], axes,
// source_ids}. Illustrative numbers only — nothing here is advice.

import { register, json, notFound, type DemoRequest } from "../registry";
import { registerStream, type StreamFrame } from "../DemoEventSource";
import { DEMO_NOW_ISO, minsAgo, hoursAgo, daysAgo } from "../clock";
import { companyName } from "./persona";
import type {
  V3ChartRow,
  V3CitationRow,
  V3InstructionsSummary,
  V3ReportDetail,
  V3ReportSummary,
  V3TemplateSummary,
} from "../../api/equity-research-v3";

const PREFIX = "/api/departments/equity-research/v3";

// The one run that is mid-flight when the demo loads. Landing the app on
// ``/equity-research?id=<this>`` makes the cockpit auto-play; it also plays
// when the user opens this run from the history popover.
export const GENERATING_RUN_ID = "v3-run-msft-initiation";

// --- Helpers ----------------------------------------------------------------

function citation(
  source_id: string,
  display_index: number,
  url: string,
  title: string,
  tool_name = "web_search",
): V3CitationRow {
  return { source_id, tool_name, display_index, provenance: { url, title } };
}

function categoricalChart(
  chart_id: string,
  chart_type: "line" | "bar" | "column" | "area",
  title: string,
  points: Array<{ label: string; value: number }>,
  axes: Record<string, string>,
  source_ids: string[],
): V3ChartRow {
  return {
    chart_id,
    chart_type,
    title,
    spec: { data: points, axes, source_ids },
    rendered_url: null,
    version: 1,
  };
}

function pieChart(
  chart_id: string,
  title: string,
  points: Array<{ label: string; value: number }>,
  source_ids: string[],
): V3ChartRow {
  return {
    chart_id,
    chart_type: "pie",
    title,
    spec: { data: points, source_ids },
    rendered_url: null,
    version: 1,
  };
}

// ===========================================================================
// 1) NVIDIA (NVDA) — Initiation  [FULLY RENDERED — the showcase report]
// ===========================================================================

const NVDA_DETAIL: V3ReportDetail = {
  report: {
    report_id: "v3-run-nvda-initiation",
    subject: `${companyName("NVDA")} (NVDA) — Initiation`,
    template_id: "initiation_default",
    language: "en",
    length: "elaborative",
    status: "completed",
    created_at: daysAgo(3),
    completed_at: daysAgo(3),
    reasoning_effort: "high",
  },
  error_message: null,
  cover: {
    subtitle: "Data-center compute at the center of the AI build-out",
    tagline:
      "The reference platform for accelerated computing, priced for durable share but not for flawless execution.",
    tldr: [
      "Data-center revenue now dwarfs gaming; the franchise is an AI-infrastructure story first.",
      "CUDA plus a full-rack roadmap (GPU, networking, systems) widens the moat beyond raw silicon.",
      "Key risks: customer concentration, an accelerating competitive response, and export-control headline risk.",
    ],
    key_metrics: [
      { label: "Rating", value: "Overweight", tone: "positive" },
      { label: "Price target", value: "$205", change: "+16% vs. last", tone: "positive" },
      { label: "FY26E revenue", value: "$196B", change: "+38% y/y", tone: "positive" },
      { label: "DC gross margin", value: "~74%", tone: "neutral" },
    ],
    rating: "Overweight",
    upside_pct: 16.3,
  },
  sections: [
    {
      section_id: "thesis",
      section_index: 0,
      title: "Investment thesis",
      version: 1,
      markdown:
        "We initiate coverage of NVIDIA at **Overweight** with a $205 price target. The " +
        "franchise has shifted decisively from a gaming-GPU vendor into the reference " +
        "platform for accelerated computing, and data-center compute is now the dominant " +
        "driver of revenue and mix [^web_1]. Our constructive stance rests on three " +
        "pillars: a full-stack roadmap that pairs leading silicon with networking and " +
        "systems, a software moat in CUDA that raises switching costs, and a multi-year " +
        "capital-spending cycle among the largest cloud operators [^web_2].\n\n" +
        "The composition of revenue tells the story better than any single number. " +
        "Data-center now overwhelms the legacy segments:\n\n{{chart:rev_mix}}\n\n" +
        "We size the reward-to-risk as favorable but not one-sided. Consensus already " +
        "embeds heroic growth, so the debate is less about direction and more about the " +
        "durability of margins and the pace at which credible competition arrives [^eod_1].",
    },
    {
      section_id: "financials",
      section_index: 1,
      title: "Financial trajectory",
      version: 1,
      markdown:
        "Revenue has compounded at a pace that is rare at this scale. Our model has the " +
        "top line moving from the low-$100Bs toward ~$196B in FY26E, with data-center " +
        "carrying the growth [^eod_1].\n\n{{chart:rev_trend}}\n\n" +
        "Gross margin is the more contested line. Data-center gross margin has run in the " +
        "low-to-mid 70s, well above the corporate average, and we expect only modest " +
        "normalization as supply loosens and the mix broadens into systems [^web_2]. " +
        "Operating leverage remains substantial: R&D and go-to-market scale far more " +
        "slowly than revenue, so incremental margins stay high even as the absolute " +
        "spend rises.",
    },
    {
      section_id: "moat",
      section_index: 2,
      title: "Competitive moat",
      version: 1,
      markdown:
        "The durable advantage is the combination of silicon leadership and the CUDA " +
        "software ecosystem. A decade of libraries, tooling, and developer mindshare " +
        "means the switching cost is measured in re-engineering effort, not just unit " +
        "price [^web_3]. The move up the stack — from chips to networking to full racks " +
        "— extends that lock-in from the die to the data-center row.\n\n" +
        "Competition is real and rising: merchant accelerators, hyperscaler in-house " +
        "silicon, and open software stacks all target the same budget. We treat these as " +
        "margin-normalizing rather than share-collapsing over our forecast horizon.",
    },
    {
      section_id: "risks",
      section_index: 3,
      title: "Risks to the call",
      version: 1,
      markdown:
        "Three risks dominate. First, **customer concentration**: a handful of large " +
        "cloud buyers drive a disproportionate share of data-center revenue, so a pause " +
        "in their capital plans would be felt quickly [^web_1]. Second, **competitive " +
        "response**: credible in-house and merchant alternatives could compress pricing " +
        "faster than we model. Third, **policy**: export controls introduce headline and " +
        "revenue risk in specific regions [^web_3]. A valuation that already discounts " +
        "strong growth leaves less room for any of these to surprise negatively.",
    },
    {
      section_id: "valuation",
      section_index: 4,
      title: "Valuation",
      version: 1,
      markdown:
        "Our $205 target is set on a forward earnings multiple we view as defensible " +
        "given the growth and margin profile, cross-checked against a peer band of " +
        "large-cap semiconductor and AI-infrastructure names [^eod_1]. The bull case " +
        "extends the capex cycle and holds margins; the bear case normalizes both faster " +
        "than consensus. At the current price the setup skews modestly positive, which " +
        "supports an Overweight rather than a more aggressive stance.",
    },
  ],
  charts: [
    categoricalChart(
      "rev_mix",
      "bar",
      "Revenue by segment (FY26E, $B)",
      [
        { label: "Data center", value: 172 },
        { label: "Gaming", value: 12 },
        { label: "Pro visualization", value: 6 },
        { label: "Automotive", value: 4 },
        { label: "OEM & other", value: 2 },
      ],
      { x: "Segment", y: "Revenue ($B)" },
      ["eod_1"],
    ),
    categoricalChart(
      "rev_trend",
      "line",
      "Total revenue trajectory ($B)",
      [
        { label: "FY22", value: 27 },
        { label: "FY23", value: 27 },
        { label: "FY24", value: 61 },
        { label: "FY25", value: 130 },
        { label: "FY26E", value: 196 },
      ],
      { x: "Fiscal year", y: "Revenue ($B)" },
      ["eod_1"],
    ),
  ],
  citations: [
    citation(
      "web_1",
      1,
      "https://example.com/demo/nvidia-datacenter-mix",
      "Data-center now the dominant NVIDIA segment (illustrative)",
    ),
    citation(
      "web_2",
      2,
      "https://example.com/demo/accelerated-computing-roadmap",
      "Full-stack accelerated-computing roadmap (illustrative)",
    ),
    citation(
      "web_3",
      3,
      "https://example.com/demo/ai-accelerator-competition",
      "The competitive landscape for AI accelerators (illustrative)",
    ),
    citation(
      "eod_1",
      4,
      "https://example.com/demo/nvda-fundamentals",
      "NVDA fundamentals snapshot (illustrative)",
      "eodhd_fundamentals",
    ),
  ],
};

// ===========================================================================
// 2) Apple (AAPL) — Q3 Update  [rendered, lighter]
// ===========================================================================

const AAPL_DETAIL: V3ReportDetail = {
  report: {
    report_id: "v3-run-aapl-q3-update",
    subject: `${companyName("AAPL")} (AAPL) — Q3 Update`,
    template_id: "update_default",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: hoursAgo(30),
    completed_at: hoursAgo(30),
    reasoning_effort: "medium",
  },
  error_message: null,
  cover: {
    subtitle: "Services resilience offsets a maturing hardware cycle",
    tagline: "A steadier, higher-margin franchise than the unit-growth debate implies.",
    tldr: [
      "Services keeps compounding and lifts blended gross margin.",
      "iPhone units are roughly flat; the story is mix and installed-base monetization.",
      "Capital returns remain a meaningful component of total shareholder return.",
    ],
    key_metrics: [
      { label: "Rating", value: "Neutral", tone: "neutral" },
      { label: "Price target", value: "$240", change: "+3% vs. last", tone: "positive" },
      { label: "Services growth", value: "+13% y/y", tone: "positive" },
      { label: "Gross margin", value: "~46%", tone: "positive" },
    ],
    rating: "Neutral",
    upside_pct: 2.8,
  },
  sections: [
    {
      section_id: "quarter",
      section_index: 0,
      title: "The quarter in brief",
      version: 1,
      markdown:
        "The print reinforced the shift toward a services-led margin story. Product " +
        "revenue was broadly stable while Services extended its double-digit growth, " +
        "lifting blended gross margin toward the high-40s [^web_1]. The installed base " +
        "continues to widen, which is the real engine behind the recurring line.\n\n" +
        "{{chart:seg_growth}}\n\nManagement commentary pointed to steady demand and a " +
        "disciplined cost posture; nothing in the quarter changes the medium-term shape " +
        "of the model [^web_2].",
    },
    {
      section_id: "outlook",
      section_index: 1,
      title: "Outlook & rating",
      version: 1,
      markdown:
        "We hold a **Neutral** rating with a $240 target. The franchise is high quality " +
        "and defensive, but at the current multiple the risk-reward is balanced: the " +
        "upside from further services mix is partly offset by a maturing hardware cycle " +
        "and demanding valuation [^eod_1]. Capital returns remain a steady contributor to " +
        "total return, which underpins the downside.",
    },
  ],
  charts: [
    categoricalChart(
      "seg_growth",
      "column",
      "Segment growth, y/y (%)",
      [
        { label: "iPhone", value: 1 },
        { label: "Mac", value: 4 },
        { label: "iPad", value: -3 },
        { label: "Wearables", value: 2 },
        { label: "Services", value: 13 },
      ],
      { x: "Segment", y: "Growth (%)" },
      ["eod_1"],
    ),
  ],
  citations: [
    citation(
      "web_1",
      1,
      "https://example.com/demo/apple-services-mix",
      "Services lifts Apple's blended margin (illustrative)",
    ),
    citation(
      "web_2",
      2,
      "https://example.com/demo/apple-demand-commentary",
      "Steady demand commentary (illustrative)",
    ),
    citation(
      "eod_1",
      3,
      "https://example.com/demo/aapl-fundamentals",
      "AAPL fundamentals snapshot (illustrative)",
      "eodhd_fundamentals",
    ),
  ],
};

// ===========================================================================
// 3) AI Semiconductors — Sector Thesis  [rendered, with a pie]
// ===========================================================================

const SECTOR_DETAIL: V3ReportDetail = {
  report: {
    report_id: "v3-run-ai-semis-sector",
    subject: "AI Semiconductors — Sector Thesis",
    template_id: "sector_research_default",
    language: "en",
    length: "elaborative",
    status: "completed",
    created_at: daysAgo(9),
    completed_at: daysAgo(9),
    reasoning_effort: "high",
  },
  error_message: null,
  cover: {
    subtitle: "Where the value accrues across the AI-compute stack",
    tagline: "Own the platform layer and the tightest supply-chain chokepoints.",
    tldr: [
      "Value concentrates in accelerators and the foundry/packaging chokepoints.",
      "Memory (HBM) is a genuine bottleneck and a rising share of system cost.",
      "Networking is the underappreciated second-order winner of scale-out clusters.",
    ],
    key_metrics: [
      { label: "Stance", value: "Constructive", tone: "positive" },
      { label: "Coverage", value: "12 names" },
      { label: "Top pick", value: "Accelerators", tone: "positive" },
    ],
    rating: "Constructive",
    upside_pct: null,
  },
  sections: [
    {
      section_id: "map",
      section_index: 0,
      title: "Mapping the stack",
      version: 1,
      markdown:
        "AI-compute value is not spread evenly. It pools at a few layers: the accelerator " +
        "itself, the foundry and advanced-packaging step that few can supply, the " +
        "high-bandwidth memory that has become a hard bottleneck, and the networking " +
        "fabric that stitches accelerators into clusters [^web_1]. Our estimate of where " +
        "system cost lands:\n\n{{chart:stack_value}}\n\nThe practical implication is that " +
        "exposure to the chokepoints — advanced packaging and HBM — can be as attractive " +
        "as owning the headline accelerator names [^web_2].",
    },
    {
      section_id: "picks",
      section_index: 1,
      title: "Where we lean",
      version: 1,
      markdown:
        "We are most constructive on the platform layer (accelerators plus their software " +
        "ecosystems) and on the supply-chain chokepoints. Memory is a cyclical but " +
        "structurally rising share of cost, and networking is the second-order winner as " +
        "clusters scale out [^web_3]. We are more cautious on undifferentiated components " +
        "where the AI build-out does little to change competitive intensity.",
    },
  ],
  charts: [
    pieChart(
      "stack_value",
      "Share of AI system cost by layer (illustrative)",
      [
        { label: "Accelerators", value: 45 },
        { label: "Memory (HBM)", value: 20 },
        { label: "Packaging/foundry", value: 15 },
        { label: "Networking", value: 12 },
        { label: "Other", value: 8 },
      ],
      ["web_2"],
    ),
  ],
  citations: [
    citation(
      "web_1",
      1,
      "https://example.com/demo/ai-compute-value-chain",
      "Mapping the AI-compute value chain (illustrative)",
    ),
    citation(
      "web_2",
      2,
      "https://example.com/demo/advanced-packaging-hbm",
      "Advanced packaging and HBM as chokepoints (illustrative)",
    ),
    citation(
      "web_3",
      3,
      "https://example.com/demo/scale-out-networking",
      "Networking in scale-out AI clusters (illustrative)",
    ),
  ],
};

// ===========================================================================
// 4) Palantir (PLTR) — Initiation  [rendered, short]
// ===========================================================================

const PLTR_DETAIL: V3ReportDetail = {
  report: {
    report_id: "v3-run-pltr-initiation",
    subject: `${companyName("PLTR")} (PLTR) — Initiation`,
    template_id: "initiation_default",
    language: "en",
    length: "concise",
    status: "completed",
    created_at: daysAgo(1),
    completed_at: daysAgo(1),
    reasoning_effort: "medium",
  },
  error_message: null,
  cover: {
    subtitle: "Commercial acceleration meets a demanding valuation",
    tagline: "High-quality growth, priced for a lot of it.",
    tldr: [
      "Commercial segment is the swing factor; government remains the ballast.",
      "Operating margin inflection is the key to the bull case.",
      "Valuation leaves little room for execution slips.",
    ],
    key_metrics: [
      { label: "Rating", value: "Neutral", tone: "neutral" },
      { label: "Price target", value: "$150", change: "-5% vs. last", tone: "negative" },
      { label: "Revenue growth", value: "+27% y/y", tone: "positive" },
    ],
    rating: "Neutral",
    upside_pct: -5.2,
  },
  sections: [
    {
      section_id: "setup",
      section_index: 0,
      title: "The setup",
      version: 1,
      markdown:
        "We initiate at **Neutral** with a $150 target. The commercial business is " +
        "accelerating off a government base that provides ballast, and the operating-" +
        "margin trajectory is inflecting positively [^web_1]. The quality of growth is " +
        "high; the debate is entirely about price.\n\n{{chart:mix}}\n\nAt the current " +
        "multiple the market already pays for a lot of the future, so we prefer to wait " +
        "for a better entry point [^web_2].",
    },
  ],
  charts: [
    categoricalChart(
      "mix",
      "area",
      "Revenue mix, commercial vs. government ($B)",
      [
        { label: "FY23", value: 2.2 },
        { label: "FY24", value: 2.9 },
        { label: "FY25E", value: 3.7 },
      ],
      { x: "Fiscal year", y: "Revenue ($B)" },
      ["web_1"],
    ),
  ],
  citations: [
    citation(
      "web_1",
      1,
      "https://example.com/demo/palantir-commercial-accel",
      "Commercial acceleration at Palantir (illustrative)",
    ),
    citation(
      "web_2",
      2,
      "https://example.com/demo/palantir-valuation",
      "Valuation leaves little room (illustrative)",
    ),
  ],
};

// ===========================================================================
// 5) Microsoft (MSFT) — Initiation  [THE GENERATING RUN]
//    Streams live via the cockpit, then this finished detail is served
//    from the run.completed frame onward.
// ===========================================================================

const MSFT_SUBJECT = `${companyName("MSFT")} (MSFT) — Initiation`;

const MSFT_DETAIL: V3ReportDetail = {
  report: {
    report_id: GENERATING_RUN_ID,
    subject: MSFT_SUBJECT,
    template_id: "initiation_default",
    language: "en",
    length: "normal",
    status: "completed",
    created_at: minsAgo(2),
    completed_at: DEMO_NOW_ISO,
    reasoning_effort: "high",
  },
  error_message: null,
  cover: {
    subtitle: "Cloud and AI copilots anchor a durable software franchise",
    tagline: "A broad platform compounding through the enterprise AI cycle.",
    tldr: [
      "Azure is the growth engine; AI services are an accelerant, not the whole story.",
      "Copilot attach across the productivity suite is the monetization lever to watch.",
      "Balance-sheet strength and recurring revenue underpin the downside.",
    ],
    key_metrics: [
      { label: "Rating", value: "Overweight", tone: "positive" },
      { label: "Price target", value: "$560", change: "+9% vs. last", tone: "positive" },
      { label: "Cloud growth", value: "+21% y/y", tone: "positive" },
      { label: "Operating margin", value: "~45%", tone: "positive" },
    ],
    rating: "Overweight",
    upside_pct: 9.2,
  },
  sections: [
    {
      section_id: "overview",
      section_index: 0,
      title: "Overview",
      version: 1,
      markdown:
        "We initiate coverage of Microsoft at **Overweight** with a $560 price target. " +
        "The company pairs a durable software franchise with a cloud platform that is " +
        "compounding through the enterprise AI cycle [^web_1]. Azure is the growth " +
        "engine, and AI services layer on top of an already-broad book of recurring " +
        "revenue rather than replacing it.\n\n{{chart:cloud_trend}}\n\nThe breadth of " +
        "the portfolio — cloud, productivity, developer tools, security — is itself the " +
        "moat: few competitors touch all of those surfaces at once [^web_2].",
    },
    {
      section_id: "cloud",
      section_index: 1,
      title: "Cloud & AI",
      version: 1,
      markdown:
        "Azure growth remains the single most important number in the model. AI " +
        "workloads are additive to a base that was already expanding, and the copilot " +
        "attach across the productivity suite is the monetization lever we watch most " +
        "closely [^web_3]. Capacity is the near-term constraint, not demand.\n\n" +
        "{{chart:seg_op_income}}",
    },
    {
      section_id: "financials",
      section_index: 2,
      title: "Financials",
      version: 1,
      markdown:
        "Operating margin sits near the mid-40s and has been resilient even through a " +
        "heavy capital-spending phase to build out AI capacity [^eod_1]. Free cash flow " +
        "comfortably funds both the investment cycle and a steady capital-return " +
        "program, which limits downside at the current valuation.",
    },
    {
      section_id: "valuation",
      section_index: 3,
      title: "Valuation & risks",
      version: 1,
      markdown:
        "Our $560 target rests on a premium-but-defensible forward multiple, supported " +
        "by durable growth and best-in-class margins [^eod_1]. The main risks are a " +
        "sharper-than-expected slowdown in cloud consumption and the return profile on " +
        "the elevated AI capex. On balance the risk-reward supports an Overweight.",
    },
  ],
  charts: [
    categoricalChart(
      "cloud_trend",
      "line",
      "Cloud revenue trajectory ($B)",
      [
        { label: "FY22", value: 91 },
        { label: "FY23", value: 111 },
        { label: "FY24", value: 135 },
        { label: "FY25E", value: 163 },
      ],
      { x: "Fiscal year", y: "Revenue ($B)" },
      ["eod_1"],
    ),
    categoricalChart(
      "seg_op_income",
      "bar",
      "Operating income by segment (FY25E, $B)",
      [
        { label: "Intelligent Cloud", value: 49 },
        { label: "Productivity", value: 38 },
        { label: "More Personal Computing", value: 18 },
      ],
      { x: "Segment", y: "Operating income ($B)" },
      ["eod_1"],
    ),
  ],
  citations: [
    citation(
      "web_1",
      1,
      "https://example.com/demo/microsoft-cloud-platform",
      "Microsoft's cloud platform in the AI cycle (illustrative)",
    ),
    citation(
      "web_2",
      2,
      "https://example.com/demo/microsoft-portfolio-breadth",
      "Portfolio breadth as a moat (illustrative)",
    ),
    citation(
      "web_3",
      3,
      "https://example.com/demo/copilot-attach",
      "Copilot attach across the suite (illustrative)",
    ),
    citation(
      "eod_1",
      4,
      "https://example.com/demo/msft-fundamentals",
      "MSFT fundamentals snapshot (illustrative)",
      "eodhd_fundamentals",
    ),
  ],
};

// ---------------------------------------------------------------------------
// Run store
// ---------------------------------------------------------------------------

const FINISHED_DETAILS: V3ReportDetail[] = [
  NVDA_DETAIL,
  AAPL_DETAIL,
  SECTOR_DETAIL,
  PLTR_DETAIL,
];

const DETAILS_BY_ID = new Map<string, V3ReportDetail>(
  [...FINISHED_DETAILS, MSFT_DETAIL].map((d) => [d.report.report_id, d]),
);

// The generating run's list/detail entry reports a "running" status on load.
// Once the cockpit's stream reaches run.completed, the page re-fetches detail
// via getV3Run; we serve the finished MSFT_DETAIL by then. Since the demo has
// no server clock, we always return the finished detail from getV3Run (the
// hook only fetches detail after a terminal stream event), while the runs LIST
// keeps the "running" status so the history popover shows it mid-flight.
const RUNNING_SUMMARY: V3ReportSummary = {
  report_id: GENERATING_RUN_ID,
  subject: MSFT_SUBJECT,
  template_id: "initiation_default",
  language: "en",
  length: "normal",
  status: "running",
  created_at: minsAgo(2),
  completed_at: null,
  reasoning_effort: "high",
};

function summaryOf(detail: V3ReportDetail): V3ReportSummary {
  return {
    report_id: detail.report.report_id,
    subject: detail.report.subject,
    template_id: detail.report.template_id,
    language: detail.report.language,
    length: detail.report.length,
    status: detail.report.status,
    created_at: detail.report.created_at,
    completed_at: detail.report.completed_at,
    reasoning_effort: detail.report.reasoning_effort ?? null,
  };
}

// Newest first, generating run at the top so it's the obvious thing to open.
const RUNS_LIST: V3ReportSummary[] = [
  RUNNING_SUMMARY,
  ...FINISHED_DETAILS.map(summaryOf).sort(
    (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at),
  ),
];

// ---------------------------------------------------------------------------
// Templates & instruction profiles
// ---------------------------------------------------------------------------

const TEMPLATES: V3TemplateSummary[] = [
  {
    id: "initiation_default",
    name: "Stock Initiation",
    is_builtin: true,
    created_at: daysAgo(120),
    updated_at: daysAgo(120),
  },
  {
    id: "update_default",
    name: "Stock Update",
    is_builtin: true,
    created_at: daysAgo(120),
    updated_at: daysAgo(120),
  },
  {
    id: "sector_research_default",
    name: "Sector Research",
    is_builtin: true,
    created_at: daysAgo(120),
    updated_at: daysAgo(120),
  },
  {
    id: "tpl-house-deep-dive",
    name: "House Deep Dive",
    is_builtin: false,
    created_at: daysAgo(20),
    updated_at: daysAgo(6),
  },
];

const INSTRUCTIONS: V3InstructionsSummary[] = [
  {
    id: "instr-value-lens",
    name: "Value Lens",
    is_builtin: false,
    created_at: daysAgo(40),
    updated_at: daysAgo(11),
  },
  {
    id: "instr-growth-lens",
    name: "Growth Lens",
    is_builtin: false,
    created_at: daysAgo(35),
    updated_at: daysAgo(4),
  },
];

// ---------------------------------------------------------------------------
// SSE cockpit script for the generating run
// ---------------------------------------------------------------------------
//
// Event names + payload shapes are pinned to useV3RunStream + its test. The
// DemoEventSource delivers each frame's `data` as JSON.stringify(data), which
// the hook re-parses. Terminal frame is run.completed.

function cockpitFrames(): StreamFrame[] {
  return [
    {
      event: "run.started",
      delayMs: 400,
      data: {
        subject: MSFT_SUBJECT,
        model: "gpt-5.4",
        template_id: "initiation_default",
      },
    },
    // Discover tools, then research the subject.
    { event: "tool.called", delayMs: 500, data: { turn: 0, tool_name: "find_tools" } },
    {
      event: "tool.completed",
      delayMs: 450,
      data: { turn: 0, tool_name: "find_tools", ok: true },
    },
    {
      event: "tool.called",
      delayMs: 600,
      data: { turn: 1, tool_name: "web_search" },
    },
    {
      event: "tool.completed",
      delayMs: 650,
      data: { turn: 1, tool_name: "web_search", ok: true, source_id: "web_1" },
    },
    {
      event: "tool.called",
      delayMs: 500,
      data: { turn: 2, tool_name: "eodhd_fundamentals" },
    },
    {
      event: "tool.completed",
      delayMs: 700,
      data: { turn: 2, tool_name: "eodhd_fundamentals", ok: true, source_id: "eod_1" },
    },
    {
      event: "tool.called",
      delayMs: 500,
      data: { turn: 3, tool_name: "eodhd_valuation" },
    },
    {
      event: "tool.completed",
      delayMs: 650,
      data: { turn: 3, tool_name: "eodhd_valuation", ok: true, source_id: "eod_1" },
    },
    {
      event: "tool.called",
      delayMs: 500,
      data: { turn: 4, tool_name: "web_search" },
    },
    {
      event: "tool.completed",
      delayMs: 600,
      data: { turn: 4, tool_name: "web_search", ok: true, source_id: "web_3" },
    },
    // Draft the sections.
    {
      event: "section.written",
      delayMs: 600,
      data: { section_id: "overview", char_count: 640 },
    },
    {
      event: "chart.emitted",
      delayMs: 500,
      data: { chart_id: "cloud_trend", chart_type: "line", title: "Cloud revenue trajectory ($B)" },
    },
    {
      event: "section.written",
      delayMs: 600,
      data: { section_id: "cloud", char_count: 410 },
    },
    {
      event: "chart.emitted",
      delayMs: 500,
      data: {
        chart_id: "seg_op_income",
        chart_type: "bar",
        title: "Operating income by segment (FY25E, $B)",
      },
    },
    {
      event: "section.written",
      delayMs: 600,
      data: { section_id: "financials", char_count: 360 },
    },
    {
      event: "section.written",
      delayMs: 600,
      data: { section_id: "valuation", char_count: 420 },
    },
    // Terminal.
    {
      event: "run.completed",
      delayMs: 500,
      data: {
        section_count: 4,
        chart_count: 2,
        citation_count: 4,
        message: "Report ready.",
      },
    },
  ];
}

registerStream((url) =>
  url.pathname === `${PREFIX}/runs/${GENERATING_RUN_ID}/events` ? cockpitFrames() : null,
);

// ---------------------------------------------------------------------------
// REST routes
// ---------------------------------------------------------------------------

register([
  // List runs. Optional ?status= filter mirrors the real route.
  {
    method: "GET",
    pattern: `${PREFIX}/runs`,
    handler: (req: DemoRequest) => {
      const status = req.url.searchParams.get("status");
      const rows = status
        ? RUNS_LIST.filter((r) => r.status === status)
        : RUNS_LIST;
      return json(rows);
    },
  },

  // Report detail. The generating run resolves to its finished detail — the
  // page only calls this after the stream reaches a terminal event.
  {
    method: "GET",
    pattern: `${PREFIX}/runs/:id`,
    handler: (req: DemoRequest) => {
      const detail = DETAILS_BY_ID.get(req.params.id);
      return detail ? json(detail) : notFound();
    },
  },

  // Start a run (read-only demo): hand back a benign report id + result.
  {
    method: "POST",
    pattern: `${PREFIX}/runs`,
    handler: () =>
      json({
        report_id: "v3-run-demo-readonly",
        result: {
          status: "completed",
          subject: "Demo run",
          template_id: "initiation_default",
          message: "Demo mode is read-only; this run was not executed.",
          sections: [],
          charts: [],
          citations: [],
        },
      }),
  },

  // Async start (SSE flavor): return a fixed id; nothing runs in the demo.
  {
    method: "POST",
    pattern: `${PREFIX}/runs/start`,
    handler: () => json({ report_id: "v3-run-demo-readonly" }),
  },

  // Cancel a run: benign success (nothing to actually cancel).
  {
    method: "POST",
    pattern: `${PREFIX}/runs/:id/cancel`,
    handler: () => json({ cancelled: false }),
  },

  // Delete a run: benign 204.
  {
    method: "DELETE",
    pattern: `${PREFIX}/runs/:id`,
    handler: () => ({ status: 204 }),
  },

  // Revisions: none exist in the demo (keeps V3ChatThread's poll happy).
  {
    method: "GET",
    pattern: `${PREFIX}/runs/:id/revisions`,
    handler: () => json([]),
  },
  {
    method: "POST",
    pattern: `${PREFIX}/runs/:id/revise`,
    handler: () => json({ revision_id: "v3-rev-demo-readonly" }),
  },
  {
    method: "POST",
    pattern: `${PREFIX}/revisions/:id/cancel`,
    handler: () => json({ cancelled: false }),
  },

  // Templates.
  {
    method: "GET",
    pattern: `${PREFIX}/templates`,
    handler: () => json(TEMPLATES),
  },
  // Instruction profiles.
  {
    method: "GET",
    pattern: `${PREFIX}/instructions`,
    handler: () => json(INSTRUCTIONS),
  },
]);
