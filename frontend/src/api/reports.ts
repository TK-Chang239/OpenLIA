export type Tone = "positive" | "negative" | "neutral" | "warn";
export type DeltaDirection = "up" | "down" | "flat";

export interface Tag {
  label: string;
  tone?: Tone;
}

export interface Metric {
  label: string;
  value: string;
  delta?: string | null;
  delta_direction?: DeltaDirection | null;
  context?: string | null;
  tag?: Tag | null;
  highlight?: boolean;
  source_ids?: string[];
}

export interface ReportCover {
  title: string;
  subtitle: string;
  eyebrow?: string | null;
  ticker?: string | null;
  tagline: string;
  tldr?: string[];
  tldr_label?: string | null;
  key_metrics?: Metric[];
  // Deterministic consensus block (WS5). Populated by the server from
  // the analyst_consensus_rating / analyst_target_mean /
  // consensus_upside_pct facts. Renders on the cover hero so the market
  // verdict appears above the fold.
  consensus_rating?: string | null;
  consensus_target_mean?: number | null;
  consensus_upside_pct?: number | null;
  consensus_source_ids?: string[];
}

export interface ReportSection {
  id: string;
  title: string;
  blocks: ReportBlock[];
}

export interface PageFurniture {
  header: { left: string; right: string };
  footer: { left: string; center: string; right: string };
  disclaimer: string;
}

export interface Verdict {
  rating: string;
  previous_rating?: string | null;
  target?: string | null;
  upside?: string | null;
  as_of?: string | null;
}

export interface SparklinePoint {
  x: number;
  y: number;
}

export interface Sparkline {
  label: string;
  points: SparklinePoint[];
}

export interface Rail {
  verdict?: Verdict | null;
  quick_stats?: Metric[];
  sparkline?: Sparkline | null;
}

export interface Citation {
  id: string;
  title?: string | null;
  source?: string | null;
  url?: string | null;
  date?: string | null;
}

// ─── Block discriminated union ─────────────────────────────────────────────
export type Align = "left" | "center" | "right";
export type FormatRule =
  | "negative"
  | "positive"
  | "directional"
  | "bold"
  | "muted"
  | "tag-beat"
  | "tag-miss"
  | "tag-info";

export interface TextBlock {
  type: "text";
  content: string;
}
export interface KeyFindingBlock {
  type: "key_finding";
  content: string;
  source_ids?: string[];
}
export interface PullQuoteBlock {
  type: "pull_quote";
  text: string;
  attribution?: string | null;
  source?: string | null;
  timestamp?: string | null;
  source_ids?: string[];
}
export interface RatingBadgeBlock {
  type: "rating_badge";
  rating: string;
  previous_rating?: string | null;
  change_date?: string | null;
}
export interface MetricCardsBlock {
  type: "metric_cards";
  metrics: Metric[];
}
export interface TableHeaderSpec {
  key: string;
  label: string;
  align?: Align;
  sortable?: boolean;
  sparkline?: boolean;
}
export interface TableBlock {
  type: "table";
  title: string;
  headers: TableHeaderSpec[];
  rows: Record<string, unknown>[];
  cell_format?: Record<string, { rule: FormatRule }>;
  footnotes?: string[];
  options?: Record<string, unknown>;
}

export interface CalloutItem {
  eyebrow?: string | null;
  title: string;
  description: string;
}
export interface CalloutGridBlock {
  type: "callout_grid";
  columns?: 2 | 3 | 4;
  items: CalloutItem[];
}

export interface TimelineEvent {
  when: string;
  what: string;
  impact?: string | null;
  impact_tag?: Tag | null;
  highlight?: boolean;
}
export interface TimelineBlock {
  type: "timeline";
  title?: string | null;
  events: TimelineEvent[];
}

export interface BulletListBlock {
  type: "bullet_list";
  items: string[];
  tone?: "default" | "positive" | "negative";
}

export interface ComparisonColumn {
  title: string;
  tone?: Tone;
  items: string[];
}
export interface ComparisonSplitBlock {
  type: "comparison_split";
  left: ComparisonColumn;
  right: ComparisonColumn;
}

export interface QuoteBlock {
  type: "quote";
  text: string;
  speaker?: string | null;
  role?: string | null;
  tag?: Tag | null;
  timestamp?: string | null;
  source_ids?: string[];
}

// Charts (kept loose — existing chart renderers consume the raw shapes).
export interface ChartLikeBlock {
  type:
    | "line_chart"
    | "bar_chart"
    | "area_chart"
    | "pie_chart"
    | "candlestick_chart"
    | "waterfall_chart"
    | "scatter_plot"
    | "heatmap"
    | "treemap"
    | "combo_chart";
  [k: string]: unknown;
}

export interface GroupBlock {
  type: "group";
  columns: 1 | 2 | 3 | 4;
  blocks: ReportBlock[];
}

export type ReportBlock =
  | TextBlock
  | KeyFindingBlock
  | PullQuoteBlock
  | RatingBadgeBlock
  | MetricCardsBlock
  | TableBlock
  | CalloutGridBlock
  | TimelineBlock
  | BulletListBlock
  | ComparisonSplitBlock
  | QuoteBlock
  | ChartLikeBlock
  | GroupBlock;

export interface MetaStats {
  sources_count: number;
  sections_count: number;
  model_id?: string | null;
  tokens_used?: number | null;
  web_search_queries?: number | null;
  est_read_minutes: number;
  /** v2.3 only. "satisfied/total" of `data_fact_ids` needs (EODHD lane)
   *  / `web_fact_ids` needs (web_search lane). Null when the outline
   *  has no needs in that lane (N/A, not zero). */
  data_coverage_label?: string | null;
  data_coverage_pct?: number | null;
  web_coverage_label?: string | null;
  web_coverage_pct?: number | null;
  /** @deprecated Mirrors `web_coverage_*`. Kept while older consumers
   *  read the legacy field name. */
  narrative_coverage_label?: string | null;
  narrative_coverage_pct?: number | null;
}

// v2.2 engine payloads. Present only on reports produced by the v2.2
// pipeline (or carrying forward through revisions). The v1 path omits
// both fields, in which case the renderer simply does not display them.
import type { RunSummaryData } from "../components/equity-research/RunSummary/RunSummary";
import type { VerificationHistoryData } from "../components/equity-research/VerificationHistory/VerificationHistory";

export interface ReportSchema {
  schema_version: "2.0";
  department: string;
  generated_at?: string;
  page_furniture?: PageFurniture | null;
  cover: ReportCover;
  sections: ReportSection[];
  rail?: Rail | null;
  citations?: Citation[];
  meta_stats?: MetaStats | null;
  run_summary?: RunSummaryData | null;
  verification_history?: VerificationHistoryData | null;
}

export interface ReportDetail {
  schema: ReportSchema | null;
  expired_at: string | null;
  // Present only on tombstoned rows, so chat-history surfaces can render
  // the "no longer available" card without a second fetch.
  title?: string;
  department?: string;
  created_at?: string;
}

export async function fetchReportDetail(
  reportId: string,
): Promise<ReportDetail> {
  if (reportId.startsWith("demo-") && import.meta.env?.MODE !== "test") {
    const { getDemoReportSchema } =
      await import("../lib/earnings-update/demo-reports");
    return { schema: await getDemoReportSchema(reportId), expired_at: null };
  }
  const res = await fetch(`/api/reports/${reportId}`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(
      `fetchReport failed (${res.status} ${res.statusText ?? ""})`,
    );
  }
  return (await res.json()) as ReportDetail;
}

export async function fetchReport(reportId: string): Promise<ReportSchema> {
  const detail = await fetchReportDetail(reportId);
  if (detail.schema === null) {
    throw new Error(`report ${reportId} is expired and has no schema`);
  }
  return detail.schema;
}

export interface ReportListItem {
  id: string;
  department: string;
  report_type: string;
  title: string;
  created_at: string;
  source_session_id?: string | null;
  expired_at?: string | null;
}

export interface ReportListResponse {
  items: ReportListItem[];
}

export async function listReports(
  params: {
    department?: string;
    session_id?: string;
    include_expired?: boolean;
  } = {},
): Promise<ReportListResponse> {
  const search = new URLSearchParams();
  if (params.department) search.set("department", params.department);
  if (params.session_id) search.set("session_id", params.session_id);
  if (params.include_expired) search.set("include_expired", "true");
  const qs = search.toString();
  const res = await fetch(`/api/reports${qs ? `?${qs}` : ""}`, {
    credentials: "include",
  });
  if (!res.ok) {
    throw new Error(
      `listReports failed (${res.status} ${res.statusText ?? ""})`,
    );
  }
  return (await res.json()) as ReportListResponse;
}

export async function deleteReport(reportId: string): Promise<void> {
  const res = await fetch(`/api/reports/${reportId}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(
      `deleteReport failed (${res.status} ${res.statusText ?? ""})`,
    );
  }
}

export function reportPdfUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/pdf`;
}

export function reportDocxUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/docx`;
}

// v2.2 pipeline_run export URLs. Backend routes mirror v1 verbatim with a
// /departments/equity-research/v2/runs/{run_id}/export.{pdf,docx} prefix.
export function v2RunPdfUrl(runId: string): string {
  return `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}/export.pdf`;
}

export function v2RunDocxUrl(runId: string): string {
  return `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}/export.docx`;
}

export type DownloadFormat = "pdf" | "docx";

export interface DownloadResult {
  blob: Blob;
  filename: string;
}

export class DownloadError extends Error {
  public readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "DownloadError";
    this.status = status;
  }
}

const FILENAME_STAR_RE = /filename\*\s*=\s*([^;]+)/i;
const FILENAME_RE = /filename\s*=\s*("([^"]+)"|([^;]+))/i;

export function parseFilenameFromHeader(
  contentDisposition: string | null,
  fallback: string,
): string {
  if (!contentDisposition) return fallback;
  const star = contentDisposition.match(FILENAME_STAR_RE);
  if (star) {
    const raw = star[1].trim();
    // RFC5987: charset'lang'encoded-value
    const m = raw.match(/^([^']*)'([^']*)'(.+)$/);
    const value = m ? m[3] : raw;
    try {
      return decodeURIComponent(value);
    } catch {
      return value;
    }
  }
  const m = contentDisposition.match(FILENAME_RE);
  if (m) {
    const raw = (m[2] ?? m[3] ?? "").trim();
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  return fallback;
}

export type ReportEngine = "v1" | "v2" | "v23" | "v3" | "eu" | "mb";

// Earnings Update v2 standalone HTML render endpoint. Mirrors v3HtmlUrl
// (in equity-research-v3.ts) — the caller opens it in a new tab; the
// browser's Save As then yields a Word/PDF copy.
export function euHtmlUrl(reportId: string): string {
  return `/api/departments/earnings-update/v2/runs/${encodeURIComponent(reportId)}/html`;
}

// Morning Briefing standalone HTML render endpoint. Mirrors euHtmlUrl —
// the caller opens it in a new tab; the browser's Save As then yields a
// Word/PDF copy.
export function mbHtmlUrl(reportId: string): string {
  return `/api/departments/morning-briefing/runs/${encodeURIComponent(reportId)}/html`;
}

export async function downloadReportBlob(
  reportId: string,
  format: DownloadFormat,
  engine: ReportEngine = "v1",
): Promise<DownloadResult> {
  let url: string;
  if (engine === "v3") {
    // v3 emits both formats natively now. PDF prints the rendered
    // HTML through Playwright; docx is built by python-docx and
    // has no Playwright dependency.
    url =
      format === "pdf"
        ? `/api/departments/equity-research/v3/runs/${encodeURIComponent(reportId)}/pdf`
        : `/api/departments/equity-research/v3/runs/${encodeURIComponent(reportId)}/docx`;
  } else if (engine === "eu") {
    // Earnings Update v2 emits both formats natively, mirroring v3:
    // PDF prints the rendered HTML; docx is built by python-docx.
    url =
      format === "pdf"
        ? `/api/departments/earnings-update/v2/runs/${encodeURIComponent(reportId)}/pdf`
        : `/api/departments/earnings-update/v2/runs/${encodeURIComponent(reportId)}/docx`;
  } else if (engine === "mb") {
    // Morning Briefing emits both formats natively, mirroring EU/v3.
    url =
      format === "pdf"
        ? `/api/departments/morning-briefing/runs/${encodeURIComponent(reportId)}/pdf`
        : `/api/departments/morning-briefing/runs/${encodeURIComponent(reportId)}/docx`;
  } else if (engine === "v23") {
    // v2.3 only emits docx today; PDF is browser-print from the viewer.
    url = `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(reportId)}/docx`;
  } else if (engine === "v2") {
    url = format === "pdf" ? v2RunPdfUrl(reportId) : v2RunDocxUrl(reportId);
  } else {
    url = format === "pdf" ? reportPdfUrl(reportId) : reportDocxUrl(reportId);
  }
  const resp = await fetch(url, { credentials: "include" });
  if (!resp.ok) {
    let detail = `Download failed (${resp.status})`;
    try {
      const body = await resp.json();
      const raw = (body as { detail?: unknown } | null)?.detail;
      if (typeof raw === "string") {
        detail = raw;
      } else if (
        raw &&
        typeof raw === "object" &&
        typeof (raw as { message?: unknown }).message === "string"
      ) {
        // Tombstone/retention 410s send a structured detail dict
        // ({code, message}) — surface the specific, non-retriable message
        // rather than the generic "Download failed (410)".
        detail = (raw as { message: string }).message;
      }
    } catch {
      // body wasn't JSON; keep generic message
    }
    throw new DownloadError(resp.status, detail);
  }
  const blob = await resp.blob();
  const filename = parseFilenameFromHeader(
    resp.headers.get("content-disposition"),
    `report-${reportId}.${format}`,
  );
  return { blob, filename };
}

export function triggerBrowserSave(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5_000);
}

export function isReportExpired(row: { expired_at?: string | null }): boolean {
  return row.expired_at != null;
}
