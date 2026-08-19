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
  DeltaDirection,
  MetaStats,
  Metric,
  ReportBlock,
  ReportCover,
  ReportSchema,
  ReportSection,
  TableBlock,
  Tone,
} from "../../../api/reports";
import type {
  V3CitationRow,
  V3ChartRow,
  V3CoverMetric,
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
    cover: buildCover(detail, displayIndexById),
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
    // Legacy stored markdown may carry inline chart markers whose removal
    // leaves punctuation-only fragments ("."); never render those as
    // their own paragraphs.
    if (/^[.,;:\u2014\u2013\-\s]*$/.test(rewritten)) return;
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

function buildCover(
  detail: V3ReportDetail,
  displayIndexById: Map<string, number>,
): ReportCover {
  const eyebrow =
    TEMPLATE_EYEBROW[detail.report.template_id] ?? "Equity Research Report";
  const cover = detail.cover ?? null;
  return {
    eyebrow,
    title: detail.report.subject,
    // v1's ReportCover requires subtitle + tagline as strings. When
    // the model hasn't populated them via set_cover, fall back to
    // empty so the hero degrades to just the title + eyebrow.
    // Cover copy carries the same [^source_id] markers as section
    // markdown and must go through the same rewrite.
    subtitle: rewriteCitations(cover?.subtitle ?? "", displayIndexById),
    tagline: rewriteCitations(cover?.tagline ?? "", displayIndexById),
    tldr: (cover?.tldr ?? []).map((p) => rewriteCitations(p, displayIndexById)),
    tldr_label: "Highlights",
    key_metrics: (cover?.key_metrics ?? []).map(adaptCoverMetric),
    ticker: detail.report.subject || null,
    consensus_rating: cover?.rating ?? null,
    consensus_upside_pct:
      typeof cover?.upside_pct === "number" ? cover.upside_pct : null,
  };
}

function adaptCoverMetric(metric: V3CoverMetric): Metric {
  const direction = toneToDirection(metric.tone);
  const tone = toneToV1Tone(metric.tone);
  return {
    label: metric.label,
    value: metric.value,
    delta: metric.change ?? null,
    delta_direction: direction,
    tag: tone ? { label: "", tone } : null,
  };
}

function toneToDirection(
  tone: V3CoverMetric["tone"] | undefined,
): DeltaDirection | null {
  if (tone === "positive") return "up";
  if (tone === "negative") return "down";
  if (tone === "neutral") return "flat";
  return null;
}

function toneToV1Tone(
  tone: V3CoverMetric["tone"] | undefined,
): Tone | null {
  if (tone === "positive" || tone === "negative" || tone === "neutral") {
    return tone;
  }
  return null;
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
    const segments: Array<{ label: string; value: number }> = [];
    for (const point of data) {
      const cat = readCategorical(point);
      if (cat && cat.value > 0) segments.push(cat);
    }
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
    const points: Array<{ x: number; y: number }> = [];
    for (const point of data) {
      const xy = readXyNumeric(point);
      if (xy) points.push(xy);
    }
    if (points.length === 0) return chartPlaceholder(chart, data.length);
    return {
      type: "scatter_plot",
      title: chart.title,
      series: [{ name: chart.title, data: points }],
      source_ids: sourceIds,
    } as ChartLikeBlock;
  }

  // Bar / column / area / line: ``categories + series[].values``.
  // Walk each point individually instead of inferring the shape from
  // data[0] — v3 emits a permissive ChartDataPoint with both
  // ``{label, value}`` and ``{x, y}`` slots, and the model
  // occasionally mixes them within one chart. Per-point dispatch
  // tolerates that. Points whose value coerces to NaN (e.g. "$100M"
  // with units) are dropped so they don't poison the y-axis math
  // downstream.
  const axes = (spec.axes as Record<string, string> | undefined) ?? {};
  const fallbackName = axes.y ?? "Value";
  // Points may carry a ``series`` name; group per series over a shared,
  // first-seen-ordered category axis. Without one, everything lands in a
  // single series — the pre-multi-series behavior.
  const categories: string[] = [];
  const catIndex = new Map<string, number>();
  const seriesOrder: string[] = [];
  const seriesValues = new Map<string, Array<number | null>>();
  for (const point of data) {
    const reading = readCategorical(point);
    if (!reading) continue;
    const rawSeries = (point as { series?: unknown }).series;
    const seriesKey =
      typeof rawSeries === "string" && rawSeries.trim() ? rawSeries.trim() : fallbackName;
    if (!catIndex.has(reading.label)) {
      catIndex.set(reading.label, categories.length);
      categories.push(reading.label);
    }
    if (!seriesValues.has(seriesKey)) {
      seriesValues.set(seriesKey, []);
      seriesOrder.push(seriesKey);
    }
    const values = seriesValues.get(seriesKey)!;
    const idx = catIndex.get(reading.label)!;
    while (values.length < idx) values.push(null);
    values[idx] = reading.value;
  }
  if (seriesOrder.length === 0) return chartPlaceholder(chart, data.length);
  const series = seriesOrder.map((name) => {
    const values = seriesValues.get(name)!;
    while (values.length < categories.length) values.push(null);
    return { name, values };
  });
  return {
    type: blockType,
    title: chart.title,
    categories,
    series,
    source_ids: sourceIds,
  } as ChartLikeBlock;
}

/**
 * Read a categorical/labeled point. Accepts both ``{label, value}``
 * and the ``{x, y}`` fallback (the v3 ChartDataPoint allows both
 * slots and the model occasionally mixes them within one chart).
 * Returns ``null`` when the value doesn't survive numeric coercion —
 * NaN points poison Math.min/max downstream and silently break the
 * chart.
 */
function readCategorical(
  point: unknown,
): { label: string; value: number } | null {
  if (!point || typeof point !== "object") return null;
  const p = point as Record<string, unknown>;
  const labelSource = p.label ?? p.x;
  const valueSource = p.value ?? p.y;
  if (labelSource == null) return null;
  const value = toFiniteNumber(valueSource);
  if (value == null) return null;
  return { label: String(labelSource), value };
}

/** Read an XY point for scatter, dropping non-finite numerics. */
function readXyNumeric(point: unknown): { x: number; y: number } | null {
  if (!point || typeof point !== "object") return null;
  const p = point as Record<string, unknown>;
  const x = toFiniteNumber(p.x);
  const y = toFiniteNumber(p.y ?? p.value);
  if (x == null || y == null) return null;
  return { x, y };
}


/**
 * Coerce a value to a finite number. Tolerates numeric strings
 * ("100", "1,234.5", "$1M") by stripping common unit / separator
 * noise — the v3 ChartDataPoint schema allows string values, and the
 * model occasionally ships them with currency / scale suffixes.
 */
function toFiniteNumber(v: unknown): number | null {
  if (typeof v === "number") return Number.isFinite(v) ? v : null;
  if (typeof v !== "string") return null;
  const trimmed = v.trim();
  if (trimmed === "") return null;
  // Strip currency, percent, thousands separators, and trailing
  // scale suffixes the model sometimes attaches (1.2B, $4.5M).
  const m = trimmed.match(/^[-+]?\$?\s*([0-9][0-9,]*\.?[0-9]*)\s*([%KMBT])?$/i);
  if (!m) {
    const n = Number(trimmed);
    return Number.isFinite(n) ? n : null;
  }
  const base = Number(m[1].replace(/,/g, ""));
  if (!Number.isFinite(base)) return null;
  const suffix = (m[2] ?? "").toUpperCase();
  const sign = trimmed.startsWith("-") ? -1 : 1;
  const scale =
    suffix === "K"
      ? 1_000
      : suffix === "M"
        ? 1_000_000
        : suffix === "B"
          ? 1_000_000_000
          : suffix === "T"
            ? 1_000_000_000_000
            : 1;
  return sign * base * scale;
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

