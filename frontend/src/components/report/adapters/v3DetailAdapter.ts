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
 *   - ``{{chart:id}}`` placeholders split the prose into alternating
 *     TextBlock / ChartBlock pairs, so charts render inline at the
 *     position the model asked for instead of trailing the section.
 *   - Each ChartSpec maps to the shape the matching v1 chart
 *     component reads. Bar / column / area / line take
 *     ``categories + series[].values``; pie takes ``segments``;
 *     scatter takes ``series[].data: [{x, y}]``. Unrecognised types
 *     fall back to a TextBlock placeholder so the reader still sees
 *     the chart title and type.
 *   - Charts whose ids never appear in any section's markdown roll
 *     into a trailing "Additional charts" section — beats dropping
 *     them when the model emits one without a reference.
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
  const chartsById = new Map(detail.charts.map((c) => [c.chart_id, c]));
  const referencedChartIds = new Set<string>();

  const sections: ReportSection[] = detail.sections.map((s) => {
    const { blocks, referenced } = splitMarkdownWithCharts(
      s.markdown,
      chartsById,
      displayIndexById,
    );
    for (const id of referenced) referencedChartIds.add(id);
    return { id: s.section_id, title: s.title, blocks };
  });

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

/**
 * Walk the section markdown and emit alternating TextBlock /
 * ChartBlock entries split at each ``{{chart:id}}`` marker. A chart
 * id is consumed at most once per section so the model can't
 * inadvertently render the same chart five times by repeating the
 * marker. Returns the consumed chart ids so the caller can detect
 * unreferenced charts.
 */
function splitMarkdownWithCharts(
  markdown: string,
  chartsById: Map<string, V3ChartRow>,
  displayIndexById: Map<string, number>,
): { blocks: ReportBlock[]; referenced: string[] } {
  const blocks: ReportBlock[] = [];
  const referenced: string[] = [];
  const consumed = new Set<string>();

  CHART_REF_RE.lastIndex = 0;
  let cursor = 0;
  let match: RegExpExecArray | null;

  const pushText = (raw: string): void => {
    const rewritten = rewriteCitations(raw, displayIndexById).trim();
    if (rewritten.length === 0) return;
    blocks.push({ type: "text", content: rewritten });
  };

  while ((match = CHART_REF_RE.exec(markdown)) !== null) {
    const before = markdown.slice(cursor, match.index);
    pushText(before);
    cursor = match.index + match[0].length;

    const cid = match[1];
    if (consumed.has(cid)) continue;
    const chart = chartsById.get(cid);
    if (!chart) continue;
    consumed.add(cid);
    referenced.push(cid);
    blocks.push(chartRowToBlock(chart));
  }
  pushText(markdown.slice(cursor));
  return { blocks, referenced };
}

function rewriteCitations(
  markdown: string,
  displayIndexById: Map<string, number>,
): string {
  return markdown.replace(CITATION_RE, (_match, sid) => {
    const n = displayIndexById.get(sid);
    return n ? `[${n}]` : `[${sid}]`;
  });
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
  const sourceIds = (spec.source_ids as string[] | undefined) ?? [];

  if (chart.chart_type === "table") {
    return chartRowToTableBlock(chart, data);
  }

  const blockType = CHART_TYPE_MAP[chart.chart_type];
  if (!blockType) {
    return chartPlaceholder(chart, data.length);
  }

  // Pie expects a flat ``segments: [{label, value}]`` shape — totally
  // different from the categories/series convention the other charts
  // share.
  if (blockType === "pie_chart") {
    const segments = data
      .filter((d): d is CategoricalPoint => isCategoricalPoint(d))
      .map((d) => ({
        label: String(d.label),
        value: Number(d.value),
      }));
    if (segments.length === 0) return chartPlaceholder(chart, data.length);
    return {
      type: "pie_chart",
      title: chart.title,
      segments,
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  // Scatter expects ``series[].data: [{x, y}]`` — the categorical
  // (categories + values) shape would collapse all points onto x=0.
  if (blockType === "scatter_plot") {
    const points = data
      .filter((d): d is XyPoint => isXyPoint(d))
      .map((d) => ({ x: Number(d.x), y: Number(d.y) }))
      .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
    if (points.length === 0) return chartPlaceholder(chart, data.length);
    return {
      type: "scatter_plot",
      title: chart.title,
      series: [{ name: chart.title, data: points }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  // Bar / column / area / line: ``categories + series[].values``.
  const axes = (spec.axes as Record<string, string> | undefined) ?? {};
  const seriesName = axes.y ?? "Value";

  if (data.length > 0 && isCategoricalPoint(data[0])) {
    const categories = data.map((d) => String((d as CategoricalPoint).label));
    const values = data.map((d) => Number((d as CategoricalPoint).value));
    return {
      type: blockType,
      title: chart.title,
      categories,
      series: [{ name: seriesName, values }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  if (data.length > 0 && isXyPoint(data[0])) {
    const categories = data.map((d) => String((d as XyPoint).x));
    const values = data.map((d) => Number((d as XyPoint).y));
    return {
      type: blockType,
      title: chart.title,
      categories,
      series: [{ name: seriesName, values }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  return chartPlaceholder(chart, data.length);
}

function chartPlaceholder(chart: V3ChartRow, dataLen: number): ReportBlock {
  return {
    type: "text",
    content: `**Chart: ${chart.title}** (_${chart.chart_type}_, ${dataLen} data point${
      dataLen === 1 ? "" : "s"
    })`,
  };
}

function chartRowToTableBlock(
  chart: V3ChartRow,
  data: unknown[],
): TableBlock {
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
