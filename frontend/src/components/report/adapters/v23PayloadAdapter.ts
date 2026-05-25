/**
 * v2.3 RunPayload -> v1 ReportSchema adapter.
 *
 * The v2.3 engine produces a flatter payload than v2.2: each section is
 * an opaque prose string with `[^N]` footnote markers and `{{FIG:id}}`
 * chart placeholders, plus a separate list of ChartSpecs. The legacy
 * `ReportRenderer` (used by v1 + v2.2) wants typed blocks (text, chart,
 * …) and a citations list addressed by id.
 *
 * This adapter bridges the two so v2.3 reports render through the same
 * branded chrome — ReportCover, TableOfContents, BlockRenderer, the
 * native chart components, and the CitationsRail.
 *
 * The adapter also derives the cover hero from `thesis`:
 *   - `tldr` from `key_takeaways`
 *   - `key_metrics` from `canonical_figures`
 *   - `consensus_rating` / `consensus_upside_pct` parsed from
 *     `valuation_stance`
 *
 * Earlier revisions of this adapter also prepended `metric_cards` +
 * `key_finding` + `rating_badge` blocks to the first section. Those
 * duplicated the cover's `key_metrics`, `tldr`, and consensus block,
 * so readers saw "Key data" / "Key takeaways" twice. The adapter now
 * relies on the cover for that headline view and renders the section
 * body unadorned.
 */
import type {
  Citation,
  MetaStats,
  Metric,
  Rail,
  ReportBlock,
  ReportCover,
  ReportSchema,
  ReportSection,
  Verdict,
} from "../../../api/reports";
import type {
  V23BundleFact,
  V23BundleSeriesPoint,
  V23ChartSpec,
  V23ChartType,
  V23RunPayload,
} from "../../../api/equity-research-v2-3";

const REPORT_TYPE_TITLE: Record<string, string> = {
  initiation: "Stock Initiation Report",
  update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

const CHART_TYPE_MAP: Record<V23ChartType, string> = {
  line: "line_chart",
  bar: "bar_chart",
  column: "bar_chart",
  area: "area_chart",
  pie: "pie_chart",
  scatter: "scatter_plot",
  heatmap: "heatmap",
  table: "table",
};

const FIG_RE = /\{\{FIG:([a-zA-Z0-9_]+)\}\}/g;
const FOOTNOTE_RE = /\[\^(\d+)\]/g;

// Canonical analyst rating vocabulary used to extract a discrete rating
// from valuation_stance (a 1-2 sentence prose stance). Order matters:
// longer phrases first so "strong buy" wins over "buy".
const RATING_PHRASES: ReadonlyArray<[string, string]> = [
  ["strong buy", "Strong Buy"],
  ["strong sell", "Strong Sell"],
  ["overweight", "Overweight"],
  ["underweight", "Underweight"],
  ["outperform", "Outperform"],
  ["underperform", "Underperform"],
  ["accumulate", "Accumulate"],
  ["reduce", "Reduce"],
  ["buy", "Buy"],
  ["sell", "Sell"],
  ["hold", "Hold"],
  ["neutral", "Neutral"],
];

const UPSIDE_RE = /([+-]?\d+(?:\.\d+)?)\s*%\s*(?:upside|downside)?/i;

export function adaptV23PayloadToSchema(payload: V23RunPayload): ReportSchema {
  const chartsBySection = new Map<string, V23ChartSpec[]>();
  for (const chart of payload.charts) {
    const list = chartsBySection.get(chart.section_id) ?? [];
    list.push(chart);
    chartsBySection.set(chart.section_id, list);
  }

  const keyMetrics = buildKeyMetrics(payload);
  const ratingFromStance = parseRating(payload.thesis.valuation_stance);
  const upsidePct = parseUpsidePct(payload.thesis.valuation_stance);

  const sections: ReportSection[] = payload.sections.map((s) => {
    const rawBody = payload.section_bodies[s.id] ?? "";
    const text = stripFiguresAndNormaliseMarkers(rawBody);
    const blocks: ReportBlock[] = [];
    if (text.trim().length > 0) {
      blocks.push({ type: "text", content: text });
    }
    const charts = chartsBySection.get(s.id) ?? [];
    for (const chart of charts) {
      blocks.push(chartSpecToBlock(chart, payload.bundle_facts));
    }
    return { id: s.id, title: s.title, blocks };
  });

  const citations: Citation[] = payload.footnotes.map((line, idx) => ({
    id: String(idx + 1),
    title: line,
  }));

  const cover: ReportCover = {
    eyebrow: REPORT_TYPE_TITLE[payload.report_type] ?? payload.report_type,
    title: payload.tickers.join(", "),
    subtitle: payload.thesis.central_argument,
    tagline: payload.thesis.valuation_stance,
    tldr: payload.thesis.key_takeaways,
    tldr_label: "Key takeaways",
    key_metrics: keyMetrics,
    ticker: payload.tickers[0] ?? null,
    consensus_rating: ratingFromStance,
    consensus_upside_pct: upsidePct,
  };

  return {
    schema_version: "2.0",
    department: "equity_research",
    cover,
    sections,
    citations,
    meta_stats: buildMetaStats(payload, citations),
    rail: buildRail(payload, keyMetrics, ratingFromStance, upsidePct),
  };
}

/** Left-rail "Report Stats" card. Counts what we can derive from the
 *  payload; leaves tokens/model unset since the v2.3 payload doesn't
 *  carry them (would require a server change to surface). */
function buildMetaStats(payload: V23RunPayload, citations: Citation[]): MetaStats {
  const wordCount = Object.values(payload.section_bodies)
    .map(stripFiguresAndNormaliseMarkers)
    .join(" ")
    .split(/\s+/)
    .filter(Boolean).length;
  // ~250 wpm is the standard adult silent-reading baseline; round up so
  // a 1-paragraph note still reads as "1 min" not "0".
  const estReadMinutes = Math.max(1, Math.round(wordCount / 250));
  const webSearchQueries = citations.filter((c) => /https?:\/\//.test(c.title ?? "")).length;
  const nc = payload.narrative_coverage;
  return {
    sections_count: payload.sections.length,
    sources_count: citations.length,
    est_read_minutes: estReadMinutes,
    web_search_queries: webSearchQueries > 0 ? webSearchQueries : null,
    tokens_used: null,
    model_id: null,
    narrative_coverage_label: nc ? `${nc.satisfied}/${nc.total}` : null,
    narrative_coverage_pct: nc ? nc.pct : null,
  };
}

/** Right-rail card. Surfaces the analyst verdict (parsed from
 *  valuation_stance) and the same canonical figures the cover shows,
 *  so the reader sees the headline numbers wherever they look. */
function buildRail(
  _payload: V23RunPayload,
  keyMetrics: Metric[],
  rating: string | null,
  upsidePct: number | null,
): Rail | null {
  const verdict: Verdict | null = rating
    ? {
        rating,
        upside: upsidePct != null ? `${upsidePct > 0 ? "+" : ""}${upsidePct.toFixed(1)}%` : null,
        as_of: null,
      }
    : null;
  // Cap quick_stats at 4 — rail real estate is tight; the cover already
  // shows the longer list.
  const quickStats = keyMetrics.slice(0, 4);
  if (verdict === null && quickStats.length === 0) return null;
  return {
    verdict,
    quick_stats: quickStats,
    sparkline: null,
  };
}

function buildKeyMetrics(payload: V23RunPayload): Metric[] {
  return payload.thesis.canonical_figures.map((cf) => {
    const fact = payload.bundle_facts[cf.fact_id];
    const delta = fact ? deltaFromSeries(fact) : null;
    return {
      label: factLabel(cf.fact_id, payload.bundle_facts),
      value: humaniseDisplay(cf.display, fact),
      ...(delta !== null
        ? {
            delta: delta.text,
            delta_direction: delta.direction,
          }
        : {}),
    } satisfies Metric;
  });
}

/** Defensive number formatter for canonical_figures display strings.
 *  The SYNTHESIZE prompt asks the LLM to emit "$60.9B" / "14.2%", but
 *  when it slips and emits a raw "60900000000" the metric card would
 *  show 11 digits and be unreadable. Detect that and reformat using
 *  the fact's unit hint (if available). Leave already-formatted strings
 *  alone — anything with a non-digit/period character is treated as
 *  the LLM's deliberate display. */
function humaniseDisplay(display: string, fact: V23BundleFact | undefined): string {
  const trimmed = (display ?? "").trim();
  if (!isRawNumeric(trimmed)) return trimmed;
  const n = Number(trimmed);
  if (!Number.isFinite(n)) return trimmed;
  const unit = (fact?.unit ?? "").toLowerCase();
  if (unit === "percent" || unit === "pct" || unit === "%") return `${n.toFixed(1)}%`;
  if (unit === "x" || unit === "multiple") return `${n.toFixed(1)}x`;
  if (unit === "bps" || unit === "basis_points") return `${Math.round(n)}bps`;
  let multiplier = 1;
  if (unit === "usd_millions" || unit === "usd_mn" || unit === "usdm") multiplier = 1_000_000;
  else if (unit === "usd_billions" || unit === "usd_bn" || unit === "usdb") multiplier = 1_000_000_000;
  const scaled = n * multiplier;
  const prefix = unit.startsWith("usd") ? "$" : "";
  return `${prefix}${magnitude(scaled)}`;
}

function isRawNumeric(s: string): boolean {
  return /^-?\d+(?:\.\d+)?$/.test(s);
}

function magnitude(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1_000_000_000_000) return `${(v / 1_000_000_000_000).toFixed(2)}T`;
  if (abs >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}B`;
  if (abs >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (abs >= 1_000) return `${(v / 1_000).toFixed(1)}K`;
  if (abs < 10 && abs > 0) return v.toFixed(2);
  return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

/** Derive a YoY-style delta from the last two points of a time-series
 *  fact. Returns null for scalar facts or single-point series. */
function deltaFromSeries(
  fact: V23BundleFact,
): { text: string; direction: "up" | "down" | "flat" } | null {
  const v = fact.value;
  if (!Array.isArray(v) || v.length < 2) return null;
  const points = v as V23BundleSeriesPoint[];
  const last = points[points.length - 1];
  const prev = points[points.length - 2];
  if (prev.value === 0) return null;
  const pct = ((last.value - prev.value) / Math.abs(prev.value)) * 100;
  const direction = pct > 0.5 ? "up" : pct < -0.5 ? "down" : "flat";
  const sign = pct > 0 ? "+" : "";
  return { text: `${sign}${pct.toFixed(1)}% YoY`, direction };
}

function parseRating(stance: string): string | null {
  const lower = stance.toLowerCase();
  for (const [phrase, label] of RATING_PHRASES) {
    if (lower.includes(phrase)) return label;
  }
  return null;
}

function parseUpsidePct(stance: string): number | null {
  const m = stance.match(UPSIDE_RE);
  if (!m) return null;
  const n = Number(m[1]);
  if (!Number.isFinite(n)) return null;
  // Only surface if the surrounding text mentions upside/downside; a
  // bare "12%" inside the stance is too ambiguous to claim as upside.
  if (!/upside|downside|implies|target/i.test(stance)) return null;
  return /downside/i.test(stance) ? -Math.abs(n) : n;
}

/** Drop `{{FIG:…}}` placeholders (charts render as their own blocks)
 *  and translate `[^N]` footnote markers to v1's `[N]` style so the
 *  CitationRefs/CitationsRail wiring lights up. */
function stripFiguresAndNormaliseMarkers(body: string): string {
  return body.replace(FIG_RE, "").replace(FOOTNOTE_RE, "[$1]");
}

function chartSpecToBlock(
  spec: V23ChartSpec,
  facts: Record<string, V23BundleFact>,
): ReportBlock {
  // Tables aren't charts — the SYNTHESIZE prompt picks `chart_type='table'`
  // when the data reads more naturally as a numeric grid (peer-comp panel,
  // key-metric snapshot). They render via the TableBlock component, which
  // wants `headers` + `rows`, not the chart shape's `categories` + `series`.
  // Routing through chartSpecToBlock here would emit a chart-shaped object
  // tagged `type:'table'` and crash TableBlock on `headers.map(...)`.
  if (spec.chart_type === "table") {
    return chartSpecToTableBlock(spec, facts);
  }
  const type = CHART_TYPE_MAP[spec.chart_type] ?? "bar_chart";
  const categories = spec.category_labels;
  const series = spec.series.map((s) => {
    const values: number[] = [];
    for (let i = 0; i < categories.length; i++) {
      const factId = s.value_fact_ids[i] ?? s.value_fact_ids[0];
      values.push(resolveValueForCategory(facts[factId], categories[i], i));
    }
    return { name: s.name, values };
  });
  return {
    type,
    title: spec.title,
    categories,
    series,
    x_label: spec.x_axis_label,
    y_label: spec.y_axis_label,
    caption: spec.claim,
  } as unknown as ReportBlock;
}


/** Mirrors `_add_chart_data_table` in `v2_3_docx.py` — same layout so the
 *  browser view and the docx render the same grid. First column is the
 *  category axis (label = `x_axis_label` or "Category"); subsequent columns
 *  are one per series, labeled by `series.name`. Each row is a category
 *  with cells resolved from `bundle_facts` the way the docx renderer does. */
function chartSpecToTableBlock(
  spec: V23ChartSpec,
  facts: Record<string, V23BundleFact>,
): ReportBlock {
  const categoryKey = "category";
  const headers = [
    { key: categoryKey, label: spec.x_axis_label || "Category" },
    ...spec.series.map((s, i) => ({ key: `c${i}`, label: s.name })),
  ];
  const rows = spec.category_labels.map((category, rowIdx) => {
    const row: Record<string, unknown> = { [categoryKey]: category };
    spec.series.forEach((s, colIdx) => {
      row[`c${colIdx}`] = resolveTableCell(s, rowIdx, facts);
    });
    return row;
  });
  return {
    type: "table",
    title: spec.title,
    headers,
    rows,
  } as unknown as ReportBlock;
}


/** Cell-value resolution mirrors `_series_cell_value` in `v2_3_docx.py`.
 *  - A series with exactly one fact_id pointing at a time-series fact
 *    pulls its values from the series points, indexed by row.
 *  - Otherwise the cell is the scalar at `value_fact_ids[rowIdx]`.
 *  - Missing fact or out-of-range index renders as blank (the empty
 *    string) — better than a `0` that would imply a real measurement. */
function resolveTableCell(
  series: { value_fact_ids: string[] },
  rowIdx: number,
  facts: Record<string, V23BundleFact>,
): number | string {
  if (series.value_fact_ids.length === 1) {
    const fact = facts[series.value_fact_ids[0]];
    if (fact && Array.isArray(fact.value)) {
      const points = fact.value as V23BundleSeriesPoint[];
      if (rowIdx < points.length) return points[rowIdx].value;
      return "";
    }
  }
  const factId = series.value_fact_ids[rowIdx];
  if (factId === undefined) return "";
  const fact = facts[factId];
  if (!fact) return "";
  if (typeof fact.value === "number" || typeof fact.value === "string") {
    return fact.value;
  }
  return "";
}

function resolveValueForCategory(
  fact: V23BundleFact | undefined,
  category: string,
  index: number,
): number {
  if (!fact) return 0;
  const v = fact.value;
  if (typeof v === "number") return v;
  if (typeof v === "string") {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }
  if (Array.isArray(v)) {
    const points = v as V23BundleSeriesPoint[];
    const hit = points.find((p) => p.period === category);
    if (hit) return hit.value;
    if (points[index]) return points[index].value;
  }
  return 0;
}

/** Prefer the engine-supplied label from bundle_facts when present —
 *  the writer set it for human display in the canonical table. Fall
 *  back to a suffix-aware humaniser for cases where the canonical
 *  figure references a fact the bundle doesn't carry (shouldn't
 *  happen in practice but defends against legacy runs). */
function factLabel(
  factId: string,
  facts: Record<string, V23BundleFact>,
): string {
  const fact = facts[factId];
  if (fact && typeof fact.label === "string" && fact.label.trim().length > 0) {
    return fact.label;
  }
  return humaniseFactId(factId);
}

// Common id suffixes -> display fragment. Picked greedily — order matters.
const SUFFIX_MAP: ReadonlyArray<[string, string]> = [
  ["_ttm", " (TTM)"],
  ["_ntm", " (NTM)"],
  ["_fy25", " FY2025"],
  ["_fy24", " FY2024"],
  ["_fy23", " FY2023"],
  ["_fy22", " FY2022"],
  ["_fy21", " FY2021"],
  ["_5y", " (5y)"],
  ["_3y", " (3y)"],
  ["_yoy", " YoY"],
  ["_qoq", " QoQ"],
];

const ACRONYMS = new Set([
  "fcf",
  "ebitda",
  "ebit",
  "eps",
  "roic",
  "roe",
  "roa",
  "pe",
  "pb",
  "ps",
  "fpe",
  "dcf",
]);

function humaniseFactId(id: string): string {
  let working = id;
  let suffix = "";
  for (const [tail, sfx] of SUFFIX_MAP) {
    if (working.toLowerCase().endsWith(tail)) {
      suffix = sfx;
      working = working.slice(0, working.length - tail.length);
      break;
    }
  }
  const parts = working.split("_").filter(Boolean);
  if (parts.length === 0) return id + suffix;
  const formatted = parts.map((p, i) => {
    if (ACRONYMS.has(p.toLowerCase())) return p.toUpperCase();
    if (i === 0) return p.charAt(0).toUpperCase() + p.slice(1);
    return p.toLowerCase();
  });
  return formatted.join(" ") + suffix;
}
