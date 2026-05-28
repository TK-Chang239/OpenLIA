/**
 * v3 ReportDetail -> v1 ReportSchema adapter.
 *
 * Bridges the v3 engine's flat output (markdown sections + ChartSpecs
 * + citations rolled up by source_id) into the typed-block schema
 * v1's ``ReportRenderer`` consumes. Lets v3 reports render with the
 * shared branded chrome — ReportCover, BlockRenderer, native chart
 * components, CitationsRail — instead of a bespoke markdown dump.
 *
 * Translation rules:
 *   - ``[^source_id]`` markers in section markdown become ``[N]``
 *     where N is the citation's ``display_index``. v1's
 *     CitationsRail wiring lights up off that style.
 *   - ``{{chart:id}}`` placeholders are dropped from the prose
 *     (charts render as their own blocks). The placeholder's
 *     position is lost — the chart block lands at the end of its
 *     section. Good enough for the typical "narrative paragraph
 *     introduces the chart" pattern; revisit if v3 prompts grow
 *     mid-paragraph chart anchors.
 *   - Each ChartSpec maps to a typed v1 ChartLikeBlock when its
 *     shape is recognised (table / bar / column / line / area /
 *     pie). Unrecognised types fall back to a TextBlock placeholder
 *     so the reader still sees the chart title and type.
 *
 * Cover is intentionally lean: v3 doesn't have a thesis /
 * canonical_figures concept yet, so the cover surfaces subject +
 * template + creation date and leaves the headline metrics empty.
 * A future "v3 cover synthesis" PR can populate ``tldr`` /
 * ``key_metrics`` from a real cover-extraction step.
 */
import type {
  ChartLikeBlock,
  Citation,
  MetaStats,
  ReportBlock,
  ReportCover,
  ReportSchema,
  ReportSection,
  TableBlock,
} from "../../../api/reports";
import type {
  V3CitationRow,
  V3ChartRow,
  V3ReportDetail,
} from "../../../api/equity-research-v3";

const CITATION_RE = /\[\^([a-z0-9_]+)\]/g;
const CHART_REF_RE = /\{\{chart:([a-z0-9_]+)\}\}/g;

const TEMPLATE_EYEBROW: Record<string, string> = {
  initiation_default: "Stock Initiation Report",
  update_default: "Stock Update Report",
  sector_research_default: "Sector Research Report",
};

const CHART_TYPE_MAP: Record<string, ChartLikeBlock["type"]> = {
  line: "line_chart",
  bar: "bar_chart",
  column: "bar_chart",
  area: "area_chart",
  pie: "pie_chart",
  scatter: "scatter_plot",
};

export function adaptV3DetailToSchema(detail: V3ReportDetail): ReportSchema {
  const displayIndexById = buildDisplayIndexMap(detail.citations);
  const chartsBySectionId = buildChartsBySectionId(detail);

  const sections: ReportSection[] = detail.sections.map((s) => {
    const text = rewriteMarkers(s.markdown, displayIndexById);
    const blocks: ReportBlock[] = [];
    if (text.trim().length > 0) {
      blocks.push({ type: "text", content: text });
    }
    // Charts inferred from the markdown's {{chart:id}} placeholders
    // land in the section that referenced them. v3 doesn't track
    // chart-to-section ownership directly, so this placement comes
    // from textual reference rather than a stored FK.
    const charts = chartsBySectionId.get(s.section_id) ?? [];
    for (const chart of charts) {
      blocks.push(chartRowToBlock(chart));
    }
    return { id: s.section_id, title: s.title, blocks };
  });

  // Any chart whose id never appears in any section's markdown lands
  // in an "Additional charts" trailing section. Beats dropping them
  // silently when the LLM emits a chart it forgot to reference.
  const referencedChartIds = new Set<string>();
  for (const list of chartsBySectionId.values()) {
    for (const c of list) referencedChartIds.add(c.chart_id);
  }
  const unreferenced = detail.charts.filter(
    (c) => !referencedChartIds.has(c.chart_id),
  );
  if (unreferenced.length > 0) {
    sections.push({
      id: "__v3_extra_charts__",
      title: "Additional charts",
      blocks: unreferenced.map(chartRowToBlock),
    });
  }

  const citations: Citation[] = detail.citations
    .filter((c) => c.display_index != null)
    .sort((a, b) => (a.display_index ?? 0) - (b.display_index ?? 0))
    .map((c) => ({
      id: String(c.display_index),
      title: citationTitle(c),
      source: c.tool_name,
      url: citationUrl(c) ?? undefined,
    }));

  return {
    schema_version: "2.0",
    department: "equity_research",
    generated_at:
      detail.report.completed_at ?? detail.report.created_at ?? undefined,
    cover: buildCover(detail),
    sections,
    citations,
    meta_stats: buildMetaStats(detail, citations),
    rail: null,
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function buildDisplayIndexMap(citations: V3CitationRow[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const c of citations) {
    if (c.display_index != null) out.set(c.source_id, c.display_index);
  }
  return out;
}

/** v3 doesn't FK charts to sections. Infer placement from
 *  ``{{chart:id}}`` references in section markdown. */
function buildChartsBySectionId(
  detail: V3ReportDetail,
): Map<string, V3ChartRow[]> {
  const byId = new Map(detail.charts.map((c) => [c.chart_id, c]));
  const out = new Map<string, V3ChartRow[]>();
  for (const s of detail.sections) {
    CHART_REF_RE.lastIndex = 0;
    const seen = new Set<string>();
    let match: RegExpExecArray | null;
    while ((match = CHART_REF_RE.exec(s.markdown)) !== null) {
      const cid = match[1];
      if (seen.has(cid)) continue;
      seen.add(cid);
      const chart = byId.get(cid);
      if (!chart) continue;
      const list = out.get(s.section_id) ?? [];
      list.push(chart);
      out.set(s.section_id, list);
    }
  }
  return out;
}

function rewriteMarkers(
  markdown: string,
  displayIndexById: Map<string, number>,
): string {
  // Drop chart placeholders — charts render as their own blocks.
  let out = markdown.replace(CHART_REF_RE, "");
  // [^source_id] -> [N] so v1's CitationRefs/CitationsRail wire up.
  out = out.replace(CITATION_RE, (_match, sid) => {
    const n = displayIndexById.get(sid);
    return n ? `[${n}]` : `[${sid}]`;
  });
  return out;
}

function buildCover(detail: V3ReportDetail): ReportCover {
  const eyebrow =
    TEMPLATE_EYEBROW[detail.report.template_id] ?? "Equity Research Report";
  return {
    eyebrow,
    title: detail.report.subject,
    // ``subtitle`` + ``tagline`` are required strings on ReportCover.
    // v3 doesn't have an analyst-style headline yet, so keep them
    // empty — the cover hero renders as just the title + eyebrow.
    subtitle: "",
    tagline: "",
    tldr: [],
    tldr_label: "Highlights",
    key_metrics: [],
    ticker: detail.report.subject || null,
    consensus_rating: null,
    consensus_upside_pct: null,
  };
}

function buildMetaStats(
  detail: V3ReportDetail,
  citations: Citation[],
): MetaStats {
  const wordCount = detail.sections
    .map((s) => s.markdown)
    .join(" ")
    .split(/\s+/)
    .filter(Boolean).length;
  const estReadMinutes = Math.max(1, Math.round(wordCount / 250));
  return {
    sections_count: detail.sections.length,
    sources_count: citations.length,
    est_read_minutes: estReadMinutes,
    web_search_queries: citations.filter((c) => c.url).length,
  };
}

function citationTitle(c: V3CitationRow): string {
  const url = citationUrl(c);
  if (url) return url;
  const prov = c.provenance ?? {};
  const title = prov.title;
  if (typeof title === "string" && title.trim()) return title;
  return c.tool_name;
}

function citationUrl(c: V3CitationRow): string | null {
  const prov = c.provenance ?? {};
  const url = prov.url;
  return typeof url === "string" && url.trim() ? url : null;
}

function chartRowToBlock(chart: V3ChartRow): ReportBlock {
  const spec = chart.spec ?? {};
  const data = (spec.data as unknown[] | undefined) ?? [];
  const axes = (spec.axes as Record<string, string> | undefined) ?? {};
  const sourceIds = (spec.source_ids as string[] | undefined) ?? [];

  if (chart.chart_type === "table") {
    return chartRowToTableBlock(chart, data);
  }

  const blockType = CHART_TYPE_MAP[chart.chart_type];
  if (!blockType) {
    return {
      type: "text",
      content: `**Chart: ${chart.title}** (_${chart.chart_type}_ — preview unavailable)`,
    };
  }

  // Categorical layout: data items shaped as {label, value} (bar /
  // column / area / pie / line over discrete categories).
  if (data.length > 0 && isCategoricalPoint(data[0])) {
    const categories = data.map((d) => String((d as CategoricalPoint).label));
    const values = data.map((d) => Number((d as CategoricalPoint).value));
    const seriesName = axes.y ?? "Value";
    return {
      type: blockType,
      title: chart.title,
      categories,
      series: [{ name: seriesName, values }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  // Scatter / line layout: data items shaped as {x, y}. v1 charts
  // accept this shape via `categories` (x-axis values) + one series
  // (y values).
  if (data.length > 0 && isXyPoint(data[0])) {
    const categories = data.map((d) => String((d as XyPoint).x));
    const values = data.map((d) => Number((d as XyPoint).y));
    const seriesName = axes.y ?? "Value";
    return {
      type: blockType,
      title: chart.title,
      categories,
      series: [{ name: seriesName, values }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  // Unknown shape — surface a graceful placeholder rather than
  // crashing the renderer.
  return {
    type: "text",
    content: `**Chart: ${chart.title}** (_${chart.chart_type}_, ${data.length} data point${
      data.length === 1 ? "" : "s"
    })`,
  };
}

function chartRowToTableBlock(
  chart: V3ChartRow,
  data: unknown[],
): TableBlock {
  // Pull headers from the first row's keys; rows pass through as-is
  // (v1 TableBlock reads cells by header.key).
  const firstRow = (data[0] ?? {}) as Record<string, unknown>;
  const headerKeys = Object.keys(firstRow);
  return {
    type: "table",
    title: chart.title,
    headers: headerKeys.map((k) => ({ key: k, label: humaniseKey(k) })),
    rows: data.map((d) => d as Record<string, unknown>),
  };
}

function humaniseKey(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

interface CategoricalPoint {
  label: unknown;
  value: unknown;
}
interface XyPoint {
  x: unknown;
  y: unknown;
}

function isCategoricalPoint(v: unknown): v is CategoricalPoint {
  if (!v || typeof v !== "object") return false;
  return "label" in v && "value" in v;
}

function isXyPoint(v: unknown): v is XyPoint {
  if (!v || typeof v !== "object") return false;
  return "x" in v && "y" in v;
}
