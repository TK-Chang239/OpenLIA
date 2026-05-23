/**
 * v2 → v1 report adapter.
 *
 * The v2.2 backend emits structured `ReportV2` JSON whose block-type
 * vocabulary differs from v1's:
 *
 *   v2 type           v1 type             notes
 *   ─────────         ───────────         ────────────────────────────────
 *   prose             text                prose.text → text.content (markdown)
 *   paragraph/text/
 *   markdown/md       text                drafter aliases — same as prose
 *   headline          text                rendered as `## name` markdown
 *   subheadline       text                rendered as `### name` markdown
 *   table             table               headers[] (string) → [{key,label}],
 *                                         rows[][] → Record<key,value>
 *   kpi_strip         metric_cards        cells → metrics; delta passes
 *   quote_block       quote               quote/source/citation_id → v1 fields
 *   chart             chart_image         passthrough payload + caption
 *   skip_banner       skip_banner         pass-through (v1 block added in B1)
 *   degraded_banner   degraded_banner     pass-through
 *   excel_attachment  excel_attachment    pass-through
 *
 * Anything else is left alone so v1's BlockRenderer renders an
 * "Unsupported block type" placeholder — same fail-soft surface v1
 * already has.
 *
 * The adapter also lifts citations from `[c:id]` markers (v2) to `[N]`
 * markers (v1) using the citation manifest's first-appearance ordering,
 * so v1's CitationRefs / CitationsRail light up identically.
 */
import type { ReportBlock, ReportSchema } from "../../../api/reports";
import type { RunSummaryData } from "../../equity-research/RunSummary/RunSummary";
import type { VerificationHistoryData } from "../../equity-research/VerificationHistory/VerificationHistory";

// ─── v2 wire shape (loose typing — block payloads are untyped dicts) ─────

export interface V2Cover {
  title: string;
  eyebrow?: string | null;
  subtitle?: string | null;
  tagline?: string | null;
  ticker?: string | null;
}

export interface V2Section {
  id: string;
  name: string;
  status?: "OK" | "SKIPPED" | "DEGRADED";
  blocks: Record<string, unknown>[];
  skip_reason?: string | null;
  degraded_reason?: string | null;
}

export interface V2Citation {
  id: string;
  source_type?: string | null;
  tool?: string | null;
  url?: string | null;
  title: string;
  retrieved_at?: string | null;
  snippet?: string | null;
}

export interface ReportV2Wire {
  engine_version: string;
  generated_at: string;
  template_id: string;
  template_name: string;
  cover: V2Cover;
  sections: V2Section[];
  citations?: V2Citation[];
  run_summary?: Record<string, unknown> | null;
  verification_history?: Record<string, unknown> | null;
}

// ─── Block adapter ───────────────────────────────────────────────────────

const PROSE_ALIASES = new Set([
  "prose",
  "paragraph",
  "text",
  "markdown",
  "md",
]);

function asString(v: unknown): string {
  if (typeof v === "string") return v;
  if (v === null || v === undefined) return "";
  return String(v);
}

function adaptBlock(
  block: Record<string, unknown>,
  citationLookup: Map<string, number>,
): ReportBlock | null {
  const rawType = block.type;
  const t = typeof rawType === "string" ? rawType.toLowerCase() : rawType;

  if (typeof t === "string" && PROSE_ALIASES.has(t)) {
    const text =
      asString(block.text) ||
      asString(block.content) ||
      asString(block.markdown);
    return {
      type: "text",
      content: replaceCitationMarkers(text, citationLookup),
    } as ReportBlock;
  }

  if (t === "headline") {
    const text = asString(block.text) || asString(block.content);
    return {
      type: "text",
      content: `## ${replaceCitationMarkers(text, citationLookup)}`,
    } as ReportBlock;
  }

  if (t === "subheadline") {
    const text = asString(block.text) || asString(block.content);
    return {
      type: "text",
      content: `### ${replaceCitationMarkers(text, citationLookup)}`,
    } as ReportBlock;
  }

  if (t === "table") {
    const rawHeaders = Array.isArray(block.headers) ? block.headers : [];
    const headers = rawHeaders.map((h, i) => ({
      key: `col_${i}`,
      label: asString(h),
    }));
    const rawRows = Array.isArray(block.rows) ? block.rows : [];
    const rows = rawRows.map((r) => {
      const cells = Array.isArray(r) ? r : [];
      const out: Record<string, unknown> = {};
      cells.forEach((c, i) => {
        out[`col_${i}`] = c;
      });
      return out;
    });
    return {
      type: "table",
      title: asString(block.caption),
      headers,
      rows,
    } as ReportBlock;
  }

  if (t === "kpi_strip") {
    const rawCells = Array.isArray(block.cells) ? block.cells : [];
    const metrics = rawCells.map((c) => {
      const cell = (c ?? {}) as Record<string, unknown>;
      return {
        label: asString(cell.label),
        value: asString(cell.value),
        delta: cell.delta ? asString(cell.delta) : undefined,
      };
    });
    return { type: "metric_cards", metrics } as ReportBlock;
  }

  if (t === "quote_block") {
    const citationId = asString(block.citation_id);
    return {
      type: "quote",
      text: asString(block.quote),
      speaker: asString(block.source),
      source_ids: citationId ? [String(citationLookup.get(citationId) ?? citationId)] : [],
      // tag / role / timestamp left undefined — v1 QuoteBlock tolerates that.
    } as unknown as ReportBlock;
  }

  if (t === "chart") {
    const format = asString(block.format);
    const payload = asString(block.payload);
    const caption = block.caption ? asString(block.caption) : undefined;
    return {
      type: "chart_image",
      format: format === "svg_inline" ? "svg_inline" : "png_base64",
      payload,
      ...(caption ? { caption } : {}),
    } as unknown as ReportBlock;
  }

  if (
    t === "skip_banner" ||
    t === "degraded_banner" ||
    t === "excel_attachment"
  ) {
    // BlockRenderer recognises these v2-only kinds directly (registered in B1).
    return block as unknown as ReportBlock;
  }

  // Unknown type — let v1's BlockRenderer surface its "Unsupported" placeholder.
  return block as unknown as ReportBlock;
}

// ─── Citation manifest ──────────────────────────────────────────────────

const CITE_MARKER = /\[c:([a-zA-Z0-9_]+)\]/g;

function collectCitedIds(sections: V2Section[]): string[] {
  const seen: string[] = [];
  const set = new Set<string>();
  for (const s of sections) {
    for (const b of s.blocks) {
      const txt =
        asString((b as Record<string, unknown>).text) ||
        asString((b as Record<string, unknown>).content) ||
        asString((b as Record<string, unknown>).markdown);
      let m: RegExpExecArray | null;
      CITE_MARKER.lastIndex = 0;
      while ((m = CITE_MARKER.exec(txt)) !== null) {
        const id = m[1];
        if (!set.has(id)) {
          set.add(id);
          seen.push(id);
        }
      }
    }
  }
  return seen;
}

function buildCitationLookup(report: ReportV2Wire): Map<string, number> {
  // First-appearance ordering across sections (mirrors backend manifest).
  const order = collectCitedIds(report.sections);
  const known = new Set((report.citations ?? []).map((c) => c.id));
  const lookup = new Map<string, number>();
  let n = 1;
  for (const id of order) {
    if (!known.has(id)) continue;
    lookup.set(id, n);
    n += 1;
  }
  return lookup;
}

function replaceCitationMarkers(text: string, lookup: Map<string, number>): string {
  // Map [c:foo] → [N]; v1's TextBlock renders [N] as superscript anchors.
  return text.replace(CITE_MARKER, (whole, id: string) => {
    const n = lookup.get(id);
    return n === undefined ? whole : `[${n}]`;
  });
}

// ─── Top-level adapter ──────────────────────────────────────────────────

export function adaptReportV2ToSchema(report: ReportV2Wire): ReportSchema {
  const lookup = buildCitationLookup(report);

  const sections = report.sections.map((s) => ({
    id: s.id,
    title: s.name,
    blocks: s.blocks
      .map((b) => adaptBlock(b, lookup))
      .filter((b): b is ReportBlock => b !== null),
  }));

  // v1 Citation has {id, title, source, url, date} — map from v2 shape.
  // Order follows first-appearance via the lookup map so v1's CitationsRail
  // numbers line up with the [N] markers inserted above.
  const orderedIds = Array.from(lookup.keys());
  const byId = new Map((report.citations ?? []).map((c) => [c.id, c]));
  const citations = orderedIds
    .map((id) => byId.get(id))
    .filter((c): c is V2Citation => c !== undefined)
    .map((c, i) => ({
      id: String(i + 1),
      title: c.title,
      source: c.source_type ?? null,
      url: c.url ?? null,
      date: c.retrieved_at ?? null,
    }));

  // run_summary / verification_history shapes mirror the v2 backend Pydantic
  // models exactly, so they pass straight through (cast only — no field-by-
  // field translation). If the backend grows fields the v1 components don't
  // know about, they'll be ignored.
  const runSummary = (report.run_summary as RunSummaryData | undefined) ?? null;
  const verificationHistory =
    (report.verification_history as VerificationHistoryData | undefined) ?? null;

  return {
    schema_version: "2.0",
    department: "equity_research",
    generated_at: report.generated_at,
    cover: {
      title: report.cover.title,
      subtitle: report.cover.subtitle ?? "",
      eyebrow: report.cover.eyebrow ?? null,
      ticker: report.cover.ticker ?? null,
      tagline: report.cover.tagline ?? "",
    },
    sections,
    citations,
    meta_stats: {
      sources_count: citations.length,
      sections_count: sections.length,
      est_read_minutes: Math.max(1, Math.round(sections.length * 1.5)),
    },
    run_summary: runSummary,
    verification_history: verificationHistory,
  };
}
