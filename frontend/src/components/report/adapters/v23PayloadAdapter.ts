/**
 * v2.3 RunPayload -> v1 ReportSchema adapter.
 *
 * The v2.3 engine produces a flatter payload than v2.2: each section is
 * an opaque prose string with `[^N]` footnote markers and `{{FIG:id}}`
 * chart placeholders, plus a separate list of ChartSpecs. The legacy
 * `ReportRenderer` (used by v1 + v2.2) wants typed blocks (text, chart,
 * key_finding, metric_cards, …) and a citations list addressed by id.
 *
 * This adapter bridges the two so v2.3 reports render through the same
 * branded chrome — ReportCover, TableOfContents, BlockRenderer, the
 * native chart components, and the CitationsRail — instead of a custom
 * minimal layout that diverges from the rest of the product.
 *
 * Key decisions:
 *   - Footnote markers `[^N]` map to v1's `[N]` markers (CitationRefs
 *     parses the bracketed integer form), and `payload.footnotes[i]`
 *     becomes Citation { id: "fn-N", title: footnote_text }.
 *   - Each section gets a text block built from the section_body, plus
 *     one chart block per spec whose section_id matches. Charts the LLM
 *     placed inline via `{{FIG:id}}` are stripped from the prose; the
 *     same charts then render at the end of their section so the order
 *     of charts in the spec is preserved and unrendered charts can't
 *     orphan (which they did in the previous V23ReportView because the
 *     writer rarely emits the marker).
 *   - Cover lifts thesis fields: central_argument -> subtitle, key
 *     takeaways -> tldr bullets, valuation_stance -> tagline,
 *     canonical_figures -> key_metrics.
 */
import type {
  Citation,
  Metric,
  ReportBlock,
  ReportSchema,
  ReportSection,
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
  morning_brief: "Morning Brief",
  earnings_review: "Earnings Review",
};

const CHART_TYPE_MAP: Record<V23ChartType, string> = {
  line: "line_chart",
  bar: "bar_chart",
  column: "bar_chart",
  area: "area_chart",
  pie: "pie_chart",
  scatter: "scatter_plot",
};

const FIG_RE = /\{\{FIG:([a-zA-Z0-9_]+)\}\}/g;
const FOOTNOTE_RE = /\[\^(\d+)\]/g;

export function adaptV23PayloadToSchema(payload: V23RunPayload): ReportSchema {
  const chartsBySection = new Map<string, V23ChartSpec[]>();
  for (const chart of payload.charts) {
    const list = chartsBySection.get(chart.section_id) ?? [];
    list.push(chart);
    chartsBySection.set(chart.section_id, list);
  }

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

  const keyMetrics: Metric[] = payload.thesis.canonical_figures.map((cf) => ({
    label: factLabel(cf.fact_id, payload.bundle_facts),
    value: cf.display,
  }));

  return {
    schema_version: "2.0",
    department: "equity_research",
    cover: {
      eyebrow: REPORT_TYPE_TITLE[payload.report_type] ?? payload.report_type,
      title: payload.tickers.join(", "),
      subtitle: payload.thesis.central_argument,
      tagline: payload.thesis.valuation_stance,
      tldr: payload.thesis.key_takeaways,
      tldr_label: "Key takeaways",
      key_metrics: keyMetrics,
      ticker: payload.tickers[0] ?? null,
    },
    sections,
    citations,
  };
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
  // ReportBlock's chart variant is loosely typed (Record<string, unknown>)
  // so the concrete chart components can pick out the keys they need.
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
