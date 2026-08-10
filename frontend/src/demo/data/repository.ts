// Repository (saved-reports library) demo fixtures. Seeds a filterable
// library of saved reports spanning every department and serves report
// content so opening a row (?open=<id>) renders a real report in the viewer.
//
// Server-side filtering: the Repository page (useRepoList) drives the list
// through GET /api/repo/items?filtered=true with q / department /
// generated_from|to / saved_from|to / sort / page / page_size. This module
// reads req.url.searchParams and actually filters, sorts, and paginates the
// seed so live search works in the static demo. Facets and content endpoints
// derive from the same seed so counts and detail stay consistent.

import { register, json, notFound } from "../registry";
import { DEMO_NOW_ISO, daysAgo, hoursAgo } from "../clock";
import { companyName } from "./persona";

// ─── Types (mirror src/api/repo.ts and src/api/reports.ts) ─────────────────

type RepoEngine = "v1" | "v3" | "eu_v2" | "mb_v2";

interface RepoRow {
  id: string;
  engine: RepoEngine;
  report_id: string;
  department: string;
  title: string;
  filename: string;
  generated_at: string;
  saved_at: string;
}

interface RepoItem {
  id: string;
  report_id: string | null;
  pipeline_run_id?: string | null;
  v3_report_id?: string | null;
  eu_v2_report_id?: string | null;
  mb_v2_report_id?: string | null;
  created_at: string;
}

interface RepoFilteredList {
  items: RepoRow[];
  page: number;
  page_size: number;
  has_more: boolean;
}

interface RepoFacets {
  departments: { slug: string; count: number }[];
  total: number;
}

// Minimal slice of the ReportSchema shape (src/api/reports.ts) — enough for
// the v1 StructuredReportRenderer to draw a real cover + sections.
interface Metric {
  label: string;
  value: string;
  delta?: string | null;
  delta_direction?: "up" | "down" | "flat" | null;
  context?: string | null;
}
interface ReportBlock {
  type: string;
  [k: string]: unknown;
}
interface ReportSection {
  id: string;
  title: string;
  blocks: ReportBlock[];
}
interface ReportSchema {
  schema_version: "2.0";
  department: string;
  generated_at?: string;
  cover: {
    title: string;
    subtitle: string;
    eyebrow?: string | null;
    ticker?: string | null;
    tagline: string;
    tldr?: string[];
    tldr_label?: string | null;
    key_metrics?: Metric[];
  };
  sections: ReportSection[];
  citations?: { id: string; title?: string; source?: string; date?: string }[];
  meta_stats?: {
    sources_count: number;
    sections_count: number;
    est_read_minutes: number;
    model_id?: string | null;
  } | null;
}
interface ReportDetail {
  schema: ReportSchema | null;
  expired_at: string | null;
  title?: string;
  department?: string;
  created_at?: string;
}

// ─── Seed: 16 saved reports across all departments ─────────────────────────
// Department slugs match src/lib/department-colors.ts badge keys exactly:
// equity_research, earnings_update, morning_briefing, retail_sentiment,
// secretary, macro_research, panic_thermometer. Timestamps span ~60 days.

interface Seed {
  id: string;
  department: string;
  title: string;
  ext: "pdf" | "md" | "html";
  generatedDaysAgo: number;
  savedDaysAgo: number;
}

function fnameFrom(title: string, ext: string): string {
  const slug = title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 64);
  return `${slug}.${ext}`;
}

const SEEDS: Seed[] = [
  {
    id: "rpt-nvda-deep-dive",
    department: "equity_research",
    title: `${companyName("NVDA")} — Data-Center Accelerator Franchise Deep Dive`,
    ext: "pdf",
    generatedDaysAgo: 2,
    savedDaysAgo: 2,
  },
  {
    id: "rpt-tsmc-node-roadmap",
    department: "equity_research",
    title: `${companyName("2330.TW")} — 2nm Ramp and Foundry Pricing Power`,
    ext: "pdf",
    generatedDaysAgo: 9,
    savedDaysAgo: 8,
  },
  {
    id: "rpt-pltr-bull-bear",
    department: "equity_research",
    title: `${companyName("PLTR")} — Bull vs. Bear on Commercial AIP`,
    ext: "html",
    generatedDaysAgo: 21,
    savedDaysAgo: 20,
  },
  {
    id: "rpt-msft-cloud-margins",
    department: "equity_research",
    title: `${companyName("MSFT")} — Azure Margin Trajectory Under Capex Load`,
    ext: "pdf",
    generatedDaysAgo: 44,
    savedDaysAgo: 40,
  },
  {
    id: "rpt-aapl-q3-earnings",
    department: "earnings_update",
    title: `${companyName("AAPL")} — FQ3 Print: Services Reaccelerates`,
    ext: "pdf",
    generatedDaysAgo: 5,
    savedDaysAgo: 5,
  },
  {
    id: "rpt-googl-q2-earnings",
    department: "earnings_update",
    title: `${companyName("GOOGL")} — Q2 Recap: Search Holds, Cloud Inflects`,
    ext: "pdf",
    generatedDaysAgo: 17,
    savedDaysAgo: 16,
  },
  {
    id: "rpt-amzn-q2-earnings",
    department: "earnings_update",
    title: `${companyName("AMZN")} — Q2 Recap: AWS Growth vs. Retail Drag`,
    ext: "html",
    generatedDaysAgo: 33,
    savedDaysAgo: 30,
  },
  {
    id: "rpt-mb-2026-08-05",
    department: "morning_briefing",
    title: "Morning Briefing — Aug 5: Semis Lead, Yields Ease",
    ext: "md",
    generatedDaysAgo: 3,
    savedDaysAgo: 3,
  },
  {
    id: "rpt-mb-2026-07-22",
    department: "morning_briefing",
    title: "Morning Briefing — Jul 22: Pre-CPI Positioning",
    ext: "md",
    generatedDaysAgo: 16,
    savedDaysAgo: 16,
  },
  {
    id: "rpt-macro-fed-path",
    department: "macro_research",
    title: "Macro — Fed Path and the Front-End After the Dot Plot",
    ext: "pdf",
    generatedDaysAgo: 11,
    savedDaysAgo: 10,
  },
  {
    id: "rpt-macro-usd-liquidity",
    department: "macro_research",
    title: "Macro — Dollar Liquidity, RRP Drain, and Risk Appetite",
    ext: "pdf",
    generatedDaysAgo: 38,
    savedDaysAgo: 35,
  },
  {
    id: "rpt-rs-nvda-sentiment",
    department: "retail_sentiment",
    title: `Retail Sentiment — ${companyName("NVDA")} Chatter Around the Split`,
    ext: "html",
    generatedDaysAgo: 6,
    savedDaysAgo: 6,
  },
  {
    id: "rpt-rs-semis-basket",
    department: "retail_sentiment",
    title: "Retail Sentiment — Semis Basket Momentum and Crowding",
    ext: "html",
    generatedDaysAgo: 26,
    savedDaysAgo: 24,
  },
  {
    id: "rpt-sec-portfolio-review",
    department: "secretary",
    title: "Secretary — Weekly Portfolio Review and Action Items",
    ext: "md",
    generatedDaysAgo: 7,
    savedDaysAgo: 7,
  },
  {
    id: "rpt-sec-tax-lot-notes",
    department: "secretary",
    title: "Secretary — Tax-Lot Notes and Rebalance Candidates",
    ext: "md",
    generatedDaysAgo: 51,
    savedDaysAgo: 48,
  },
  {
    id: "rpt-panic-aug-spike",
    department: "panic_thermometer",
    title: "Panic Thermometer — Early-August Volatility Snapshot",
    ext: "pdf",
    generatedDaysAgo: 4,
    savedDaysAgo: 4,
  },
];

const ROWS: RepoRow[] = SEEDS.map((s) => ({
  id: `repoitem-${s.id}`,
  engine: "v1",
  report_id: s.id,
  department: s.department,
  title: s.title,
  filename: fnameFrom(s.title, s.ext),
  generated_at: daysAgo(s.generatedDaysAgo),
  saved_at: daysAgo(s.savedDaysAgo),
}));

// ─── Filtering / sorting / pagination ──────────────────────────────────────

/** A date-only bound (YYYY-MM-DD) as ms. `end=true` snaps to end-of-day. */
function boundMs(dateStr: string, end: boolean): number {
  const iso = end ? `${dateStr}T23:59:59.999Z` : `${dateStr}T00:00:00.000Z`;
  return Date.parse(iso);
}

function applyFilters(rows: RepoRow[], sp: URLSearchParams): RepoRow[] {
  const q = (sp.get("q") ?? "").trim().toLowerCase();
  const deptRaw = sp.get("department") ?? "";
  const depts = deptRaw
    .split(",")
    .map((d) => d.trim())
    .filter(Boolean);
  const genFrom = sp.get("generated_from") ?? "";
  const genTo = sp.get("generated_to") ?? "";
  const savedFrom = sp.get("saved_from") ?? "";
  const savedTo = sp.get("saved_to") ?? "";

  return rows.filter((r) => {
    if (q) {
      const hay = `${r.title} ${r.filename} ${r.department}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    if (depts.length > 0 && !depts.includes(r.department)) return false;
    const gen = Date.parse(r.generated_at);
    if (genFrom && gen < boundMs(genFrom, false)) return false;
    if (genTo && gen > boundMs(genTo, true)) return false;
    const saved = Date.parse(r.saved_at);
    if (savedFrom && saved < boundMs(savedFrom, false)) return false;
    if (savedTo && saved > boundMs(savedTo, true)) return false;
    return true;
  });
}

function applySort(rows: RepoRow[], sort: string): RepoRow[] {
  const out = [...rows];
  switch (sort) {
    case "saved_asc":
      out.sort((a, b) => Date.parse(a.saved_at) - Date.parse(b.saved_at));
      break;
    case "generated_desc":
      out.sort((a, b) => Date.parse(b.generated_at) - Date.parse(a.generated_at));
      break;
    case "generated_asc":
      out.sort((a, b) => Date.parse(a.generated_at) - Date.parse(b.generated_at));
      break;
    case "department_asc":
      out.sort(
        (a, b) =>
          a.department.localeCompare(b.department) ||
          Date.parse(b.saved_at) - Date.parse(a.saved_at),
      );
      break;
    case "filename_asc":
      out.sort((a, b) => a.filename.localeCompare(b.filename));
      break;
    case "saved_desc":
    default:
      out.sort((a, b) => Date.parse(b.saved_at) - Date.parse(a.saved_at));
      break;
  }
  return out;
}

function toRepoItem(r: RepoRow): RepoItem {
  return {
    id: r.id,
    report_id: r.report_id,
    pipeline_run_id: null,
    v3_report_id: null,
    eu_v2_report_id: null,
    mb_v2_report_id: null,
    created_at: r.saved_at,
  };
}

// ─── Report content (v1 ReportDetail schema) ───────────────────────────────
// Full renderable schemas for a handful of rows; the rest fall back to a
// generic-but-valid schema so every row still opens to real content.

function metric(
  label: string,
  value: string,
  delta?: string,
  dir?: "up" | "down" | "flat",
  context?: string,
): Metric {
  return {
    label,
    value,
    delta: delta ?? null,
    delta_direction: dir ?? null,
    context: context ?? null,
  };
}

function text(content: string): ReportBlock {
  return { type: "text", content };
}
function bullets(items: string[]): ReportBlock {
  return { type: "bullet_list", items };
}

const SCHEMAS: Record<string, ReportSchema> = {
  "rpt-nvda-deep-dive": {
    schema_version: "2.0",
    department: "equity_research",
    generated_at: daysAgo(2),
    cover: {
      title: `${companyName("NVDA")}`,
      subtitle: "Data-Center Accelerator Franchise Deep Dive",
      eyebrow: "Equity Research",
      ticker: "NVDA",
      tagline:
        "Illustrative sample report. The accelerator franchise anchors a durable data-center compute cycle.",
      tldr_label: "In brief",
      tldr: [
        "Accelerator demand remains supply-constrained through the sample horizon.",
        "Networking attach lifts blended content per rack in the illustrative model.",
        "Software and systems revenue smooths the historical hardware cyclicality.",
      ],
      key_metrics: [
        metric("Sample Rating", "Constructive"),
        metric("Illustrative Target", "$205", "+16%", "up", "vs. sample price"),
        metric("DC Rev Mix", "78%", "+6 pts", "up", "of sample total"),
        metric("Gross Margin", "74%", "+120 bps", "up"),
      ],
    },
    sections: [
      {
        id: "thesis",
        title: "Thesis",
        blocks: [
          text(
            "This is a demonstration report populated with illustrative data. The franchise pairs leading accelerators with a networking and systems stack, widening the content captured per deployed rack in the sample model.",
          ),
          bullets([
            "Compute: next-gen accelerators carry higher sample ASPs.",
            "Networking: switch and interconnect attach rises with cluster scale.",
            "Software: recurring systems revenue is modeled as counter-cyclical.",
          ]),
        ],
      },
      {
        id: "model",
        title: "Illustrative Model",
        blocks: [
          {
            type: "metric_cards",
            metrics: [
              metric("Sample Rev CAGR", "31%", "+3 pts", "up"),
              metric("Op Margin", "62%", "+180 bps", "up"),
              metric("FCF Conversion", "0.9x", undefined, "flat"),
            ],
          },
          text(
            "Numbers above are fictional and exist only to demonstrate the report layout. Nothing here is investment advice.",
          ),
        ],
      },
      {
        id: "risks",
        title: "Risks to the Sample View",
        blocks: [
          bullets([
            "Supply normalization could compress sample lead times.",
            "Customer concentration among hyperscalers in the illustrative book.",
            "Competitive accelerators and in-house silicon as modeled offsets.",
          ]),
        ],
      },
    ],
    citations: [
      { id: "c1", title: "Illustrative filing extract", source: "Demo", date: daysAgo(3) },
      { id: "c2", title: "Sample conference transcript", source: "Demo", date: daysAgo(6) },
    ],
    meta_stats: {
      sources_count: 8,
      sections_count: 3,
      est_read_minutes: 7,
      model_id: "demo-analyst",
    },
  },

  "rpt-aapl-q3-earnings": {
    schema_version: "2.0",
    department: "earnings_update",
    generated_at: daysAgo(5),
    cover: {
      title: `${companyName("AAPL")}`,
      subtitle: "FQ3 Print — Services Reaccelerates",
      eyebrow: "Earnings Update",
      ticker: "AAPL",
      tagline:
        "Illustrative earnings recap. Services growth offsets a flattish hardware line in the sample quarter.",
      tldr_label: "Print at a glance",
      tldr: [
        "Sample revenue lands modestly ahead of the illustrative consensus.",
        "Services reaccelerates on subscriptions in the demo dataset.",
        "Gross margin expands on mix in the fictional model.",
      ],
      key_metrics: [
        metric("Sample EPS", "$1.42", "Beat", "up", "vs. illustrative est."),
        metric("Revenue", "$88.6B", "+5%", "up", "sample YoY"),
        metric("Services", "$26.1B", "+12%", "up"),
        metric("Gross Margin", "46.9%", "+80 bps", "up"),
      ],
    },
    sections: [
      {
        id: "quarter",
        title: "The Sample Quarter",
        blocks: [
          text(
            "Demonstration recap with fictional figures. Services carried the sample quarter while hardware was roughly flat year over year in the illustrative model.",
          ),
          {
            type: "table",
            title: "Illustrative Segment Detail",
            headers: [
              { key: "seg", label: "Segment" },
              { key: "rev", label: "Revenue", align: "right" },
              { key: "yoy", label: "YoY", align: "right" },
            ],
            rows: [
              { seg: "iPhone", rev: "$39.3B", yoy: "+1%" },
              { seg: "Services", rev: "$26.1B", yoy: "+12%" },
              { seg: "Wearables", rev: "$8.1B", yoy: "-2%" },
              { seg: "Mac + iPad", rev: "$15.1B", yoy: "+4%" },
            ],
          },
        ],
      },
      {
        id: "guide",
        title: "Illustrative Guidance",
        blocks: [
          bullets([
            "Sample next-quarter revenue framed as low-single-digit growth.",
            "Services momentum expected to persist in the demo narrative.",
            "Foreign-exchange framed as a modeled headwind.",
          ]),
        ],
      },
    ],
    citations: [
      { id: "c1", title: "Sample press release", source: "Demo", date: daysAgo(5) },
    ],
    meta_stats: {
      sources_count: 4,
      sections_count: 2,
      est_read_minutes: 4,
      model_id: "demo-analyst",
    },
  },

  "rpt-mb-2026-08-05": {
    schema_version: "2.0",
    department: "morning_briefing",
    generated_at: hoursAgo(9),
    cover: {
      title: "Morning Briefing",
      subtitle: "Aug 5 — Semis Lead, Yields Ease",
      eyebrow: "Morning Briefing",
      ticker: null,
      tagline:
        "Illustrative pre-market briefing. Semiconductors lead the tape while the front end of the curve eases.",
      tldr_label: "Before the open",
      tldr: [
        "Sample futures point modestly higher pre-market.",
        "Semis outperform in the illustrative overnight tape.",
        "Ten-year yield eases a few basis points in the demo dataset.",
      ],
      key_metrics: [
        metric("S&P Futures", "+0.4%", undefined, "up"),
        metric("Nasdaq Futures", "+0.7%", undefined, "up"),
        metric("US 10Y", "4.18%", "-4 bps", "down"),
        metric("VIX", "14.6", "-3.4%", "down"),
      ],
    },
    sections: [
      {
        id: "overnight",
        title: "Overnight",
        blocks: [
          text(
            "Demonstration briefing with illustrative levels. Asian and European sample sessions were firm; semiconductor names led the fictional overnight move.",
          ),
          bullets([
            "Semis basket up in the sample tape on capex headlines.",
            "Energy roughly flat as illustrative crude holds a tight range.",
            "Rates bid, with the front end leading the demo move.",
          ]),
        ],
      },
      {
        id: "watch",
        title: "On the Radar",
        blocks: [
          bullets([
            "Sample services PMI later this morning.",
            "A pair of illustrative large-cap earnings after the close.",
            "Watch the demo dollar index for a continuation of the fade.",
          ]),
        ],
      },
    ],
    meta_stats: {
      sources_count: 6,
      sections_count: 2,
      est_read_minutes: 3,
      model_id: "demo-briefer",
    },
  },

  "rpt-macro-fed-path": {
    schema_version: "2.0",
    department: "macro_research",
    generated_at: daysAgo(11),
    cover: {
      title: "Fed Path and the Front End",
      subtitle: "After the Dot Plot",
      eyebrow: "Macro Research",
      ticker: null,
      tagline:
        "Illustrative macro note. The sample dot plot nudges the front end and steepens the demo curve.",
      tldr_label: "Key takeaways",
      tldr: [
        "Sample median dots imply a shallower cutting path.",
        "Front-end yields reprice higher in the illustrative model.",
        "Curve steepening is the modeled base case in the demo.",
      ],
      key_metrics: [
        metric("2Y Yield", "4.44%", "+6 bps", "up"),
        metric("10Y Yield", "4.18%", "-2 bps", "down"),
        metric("2s10s", "-26 bps", "+8 bps", "up"),
        metric("Terminal (sample)", "3.4%", undefined, "flat"),
      ],
    },
    sections: [
      {
        id: "read",
        title: "Reading the Sample Dots",
        blocks: [
          text(
            "Demonstration macro note using fictional figures. The illustrative projections imply fewer cuts over the sample horizon, lifting the front end relative to the demo forwards.",
          ),
          {
            type: "comparison_split",
            left: {
              title: "Hawkish read (sample)",
              tone: "negative",
              items: [
                "Sticky illustrative services inflation.",
                "Resilient demo labor market prints.",
                "Higher-for-longer framed as the base case.",
              ],
            },
            right: {
              title: "Dovish read (sample)",
              tone: "positive",
              items: [
                "Cooling illustrative rents feed shelter.",
                "Softening demo hiring breadth.",
                "Cuts pulled forward in the alt scenario.",
              ],
            },
          },
        ],
      },
      {
        id: "positioning",
        title: "Illustrative Positioning",
        blocks: [
          bullets([
            "Steepeners as the modeled expression in the demo.",
            "Front-end caution given the sample repricing.",
            "Dollar framed as range-bound in the fictional view.",
          ]),
        ],
      },
    ],
    citations: [
      { id: "c1", title: "Sample projection summary", source: "Demo", date: daysAgo(11) },
    ],
    meta_stats: {
      sources_count: 5,
      sections_count: 2,
      est_read_minutes: 5,
      model_id: "demo-macro",
    },
  },
};

/** Fallback schema so every seeded row still opens to valid content. */
function genericSchema(row: RepoRow): ReportSchema {
  return {
    schema_version: "2.0",
    department: row.department,
    generated_at: row.generated_at,
    cover: {
      title: row.title,
      subtitle: "Illustrative sample report",
      eyebrow: row.department
        .split("_")
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" "),
      ticker: null,
      tagline:
        "This is a demonstration report populated with illustrative sample data. Nothing here is real market data or investment advice.",
      tldr_label: "In brief",
      tldr: [
        "Fictional figures shown only to demonstrate the report layout.",
        "Content is generated for the OpenLIA demo environment.",
        "No real analysis, recommendation, or advice is implied.",
      ],
      key_metrics: [
        metric("Sample Signal", "Neutral", undefined, "flat"),
        metric("Confidence", "Illustrative"),
        metric("Horizon", "Demo"),
      ],
    },
    sections: [
      {
        id: "summary",
        title: "Summary",
        blocks: [
          text(
            "Demonstration content. This saved report exists to show how the Repository library and file viewer render across departments. All values are fictional.",
          ),
          bullets([
            "Filterable by department, search text, and date ranges.",
            "Sortable by saved date, generated date, department, and filename.",
            "Opens in the file viewer with a branded report layout.",
          ]),
        ],
      },
    ],
    meta_stats: {
      sources_count: 3,
      sections_count: 1,
      est_read_minutes: 2,
      model_id: "demo-analyst",
    },
  };
}

function reportDetailFor(reportId: string): ReportDetail | null {
  const row = ROWS.find((r) => r.report_id === reportId);
  if (!row) return null;
  const schema = SCHEMAS[reportId] ?? genericSchema(row);
  return {
    schema,
    expired_at: null,
    title: row.title,
    department: row.department,
    created_at: row.generated_at,
  };
}

// ─── Routes ─────────────────────────────────────────────────────────────────

register([
  // List. filtered=true => RepoFilteredList (page shape used by useRepoList).
  // Without it => { items: RepoItem[] } (legacy listRepoItems shape).
  {
    method: "GET",
    pattern: "/api/repo/items",
    handler: (req) => {
      const sp = req.url.searchParams;
      if (sp.get("filtered") !== "true") {
        return json({ items: ROWS.map(toRepoItem) });
      }
      const filtered = applyFilters(ROWS, sp);
      const sorted = applySort(filtered, sp.get("sort") ?? "saved_desc");
      const page = Math.max(1, Number.parseInt(sp.get("page") ?? "1", 10) || 1);
      const pageSize = Math.max(
        1,
        Number.parseInt(sp.get("page_size") ?? "50", 10) || 50,
      );
      const start = (page - 1) * pageSize;
      const items = sorted.slice(start, start + pageSize);
      const body: RepoFilteredList = {
        items,
        page,
        page_size: pageSize,
        has_more: start + pageSize < sorted.length,
      };
      return json(body);
    },
  },

  // Facets: department counts + total (across the whole seed, unfiltered).
  {
    method: "GET",
    pattern: "/api/repo/facets",
    handler: () => {
      const counts = new Map<string, number>();
      for (const r of ROWS) counts.set(r.department, (counts.get(r.department) ?? 0) + 1);
      const departments = [...counts.entries()]
        .map(([slug, count]) => ({ slug, count }))
        .sort((a, b) => b.count - a.count || a.slug.localeCompare(b.slug));
      const facets: RepoFacets = { departments, total: ROWS.length };
      return json(facets);
    },
  },

  // Report detail (viewer content). GET /api/reports/:id -> ReportDetail.
  {
    method: "GET",
    pattern: "/api/reports/:id",
    handler: (req) => {
      const detail = reportDetailFor(req.params.id);
      return detail ? json(detail) : notFound("report_not_found");
    },
  },

  // Capabilities manifest — the report renderers fetch this to decide
  // dev_mode; register defensively so the call resolves cleanly in the demo.
  {
    method: "GET",
    pattern: "/api/capabilities",
    handler: () =>
      json({
        engine_version: "demo",
        dev_mode: false,
        supported: [],
        unsupported: [],
      }),
  },

  // Read-only mutations. Save/unsave/delete all resolve benignly; the seed
  // is not mutated. Covers v1 plus the v3/eu/mb/v2 engine mirror surfaces.
  {
    method: "POST",
    pattern: "/api/repo/items",
    handler: (req) => {
      const body = (req.body ?? {}) as { report_id?: string };
      const id = body.report_id ?? "demo-report";
      const item: RepoItem = {
        id: `repoitem-${id}`,
        report_id: id,
        pipeline_run_id: null,
        v3_report_id: null,
        eu_v2_report_id: null,
        mb_v2_report_id: null,
        created_at: DEMO_NOW_ISO,
      };
      return json(item, 201);
    },
  },
  {
    method: "DELETE",
    pattern: "/api/repo/items",
    handler: () => json({ ok: true }),
  },
  {
    method: "DELETE",
    pattern: "/api/reports/:id",
    handler: () => json({ ok: true }),
  },

  // Engine-specific repo mirrors (POST save / DELETE unsave / GET saved-list).
  { method: "POST", pattern: "/api/repo/v2-runs", handler: () => json({ ok: true }, 201) },
  { method: "DELETE", pattern: "/api/repo/v2-runs", handler: () => json({ ok: true }) },
  {
    method: "GET",
    pattern: "/api/repo/v2-runs",
    handler: () => json({ saved_run_ids: [] }),
  },
  { method: "POST", pattern: "/api/repo/v3-runs", handler: () => json({ ok: true }, 201) },
  { method: "DELETE", pattern: "/api/repo/v3-runs", handler: () => json({ ok: true }) },
  {
    method: "GET",
    pattern: "/api/repo/v3-runs",
    handler: () => json({ saved_report_ids: [] }),
  },
  { method: "POST", pattern: "/api/repo/eu-runs", handler: () => json({ ok: true }, 201) },
  { method: "DELETE", pattern: "/api/repo/eu-runs", handler: () => json({ ok: true }) },
  {
    method: "GET",
    pattern: "/api/repo/eu-runs",
    handler: () => json({ saved_report_ids: [] }),
  },
  { method: "POST", pattern: "/api/repo/mb-runs", handler: () => json({ ok: true }, 201) },
  { method: "DELETE", pattern: "/api/repo/mb-runs", handler: () => json({ ok: true }) },
  {
    method: "GET",
    pattern: "/api/repo/mb-runs",
    handler: () => json({ saved_report_ids: [] }),
  },
]);
