/**
 * v3 equity-research client.
 *
 * Matches the six endpoints exposed by
 * `packages/server/.../routes/departments/equity_research_v3.py`:
 *
 *   POST   /api/departments/equity-research/v3/runs
 *   GET    /api/departments/equity-research/v3/runs
 *   GET    /api/departments/equity-research/v3/runs/{id}
 *   DELETE /api/departments/equity-research/v3/runs/{id}
 *   GET    /api/departments/equity-research/v3/runs/{id}/html
 *   GET    /api/departments/equity-research/v3/runs/{id}/pdf
 *
 * All endpoints are gated server-side by REPORT_ENGINE_VERSION=v3.
 * When the flag is unset every call returns HTTP 503 with a clear
 * `detail` body — the UI surfaces that as a "v3 engine disabled"
 * banner and gates the entry point.
 *
 * No SSE in this surface yet — runs return synchronously after the
 * full tool-use loop completes (typically 1-5 min). Phase 3b will
 * add a streaming endpoint and switch the client to incremental
 * updates.
 */
import { request } from "./_request";

const PREFIX = "/api/departments/equity-research/v3";

export type V3Language = "en" | "zh-TW";
export type V3ReportLength = "concise" | "normal" | "elaborative";
export type V3ReportType = "initiation" | "update" | "sector_research";
export type V3RunStatus = "placeholder" | "running" | "completed" | "failed";
// Three-state extended-thinking knob. ``"off"`` is the UI-only
// representation; the wire payload sends ``null`` for off and
// the literal ``"medium"`` / ``"high"`` for the other two.
export type V3ReasoningEffort = "off" | "medium" | "high";
export type V3ChartType =
  | "line"
  | "bar"
  | "column"
  | "area"
  | "pie"
  | "scatter"
  | "table";

export interface V3StartPayload {
  subject: string;
  language?: V3Language;
  length?: V3ReportLength;
  report_type?: V3ReportType;
  // When set, resolves against ``report_v3_templates`` (built-in or
  // user upload). When omitted, the server falls back to the
  // ``report_type`` default built-in.
  template_id?: string | null;
  provider_kind: string;
  model: string;
  // Wire enum has "medium" | "high" only; the UI's "off" maps to
  // ``null`` (the field is dropped from the payload) and the server's
  // ReasoningEffort default leaves thinking off on the adapter side.
  reasoning_effort?: "medium" | "high" | null;
}

export interface V3TemplateSummary {
  id: string;
  name: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

export interface V3TemplateCreatePayload {
  name: string;
  markdown: string;
  source_doc_blob?: string | null;
  source_doc_mime?: string | null;
}

export interface V3Section {
  section_id: string;
  title: string;
  markdown: string;
}

export interface V3Chart {
  chart_id: string;
  chart_type: V3ChartType;
  title: string;
  data: unknown[];
  axes?: Record<string, string>;
  source_ids?: string[];
}

export interface V3CitationLogEntry {
  source_id: string;
  tool_name: string;
  arguments: Record<string, unknown>;
  result_summary: string;
  provenance: Record<string, unknown>;
  timestamp: string;
  input_tokens: number;
  output_tokens: number;
  wall_time_ms: number;
}

export interface V3RunResult {
  status: V3RunStatus;
  subject: string;
  template_id: string;
  message: string;
  sections: V3Section[];
  charts: V3Chart[];
  citations: V3CitationLogEntry[];
}

export interface V3StartResponse {
  report_id: string;
  result: V3RunResult;
}

export interface V3StartAsyncResponse {
  report_id: string;
}

// Event taxonomy mirrors `packages/core/.../report_v3/events.py`.
// Keep this in lockstep — the streaming page treats unknown event
// types as no-ops, but typed events keep the activity feed strict.
export type V3EventType =
  | "run.started"
  | "tool.called"
  | "tool.completed"
  | "section.written"
  | "chart.emitted"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "run.snapshot";

export interface V3Event {
  type: V3EventType;
  payload: Record<string, unknown>;
}

export const V3_TERMINAL_EVENT_TYPES: ReadonlySet<V3EventType> = new Set([
  "run.completed",
  "run.failed",
  "run.cancelled",
  "run.snapshot",
]);

export interface V3ReportSummary {
  report_id: string;
  subject: string;
  template_id: string;
  language: string;
  length: string;
  status: string;
  created_at: string;
  completed_at: string | null;
  /** "medium" | "high" when reasoning was on at dispatch; null
   *  when it was off. Persisted on the row so the chat-thread
   *  Reasoning chip survives page reload. */
  reasoning_effort?: string | null;
}

export interface V3SectionRow {
  section_id: string;
  section_index: number;
  title: string;
  markdown: string;
  /** 1 = original-run content; >1 = touched by a revision. */
  version: number;
}

export interface V3ChartRow {
  chart_id: string;
  chart_type: string;
  title: string;
  spec: Record<string, unknown>;
  rendered_url: string | null;
  version: number;
}

export interface V3Revision {
  id: string;
  report_id: string;
  revision_index: number;
  request: string;
  status: "running" | "completed" | "failed" | "cancelled";
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface V3RevisionStartResponse {
  revision_id: string;
}

export interface V3CitationRow {
  source_id: string;
  tool_name: string;
  display_index: number | null;
  provenance: Record<string, unknown>;
}

export interface V3CoverMetric {
  label: string;
  value: string;
  change?: string | null;
  tone?: "positive" | "negative" | "neutral" | null;
}

/** Cover hero content populated by the model's set_cover tool call.
 *  All fields are optional; null/empty fields render as the bare
 *  cover (subject + template-derived eyebrow only). */
export interface V3CoverSpec {
  subtitle?: string | null;
  tagline?: string | null;
  tldr: string[];
  key_metrics: V3CoverMetric[];
  rating?: string | null;
  upside_pct?: number | null;
}

export interface V3ReportDetail {
  report: V3ReportSummary;
  error_message: string | null;
  sections: V3SectionRow[];
  charts: V3ChartRow[];
  citations: V3CitationRow[];
  /** Null for runs where set_cover was never called (older reports
   *  + early v3 runs). When present, the side viewer's ReportCover
   *  surfaces the tagline / TLDR / key_metrics / rating panel. */
  cover?: V3CoverSpec | null;
}

// ---------------------------------------------------------------------------
// REST surface
// ---------------------------------------------------------------------------

export function startV3Run(payload: V3StartPayload): Promise<V3StartResponse> {
  return request<V3StartResponse>(`${PREFIX}/runs`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listV3Runs(options: { status?: string } = {}): Promise<V3ReportSummary[]> {
  const params = new URLSearchParams();
  if (options.status) params.set("status", options.status);
  const qs = params.toString();
  const url = qs ? `${PREFIX}/runs?${qs}` : `${PREFIX}/runs`;
  return request<V3ReportSummary[]>(url);
}

export function getV3Run(reportId: string): Promise<V3ReportDetail> {
  return request<V3ReportDetail>(`${PREFIX}/runs/${encodeURIComponent(reportId)}`);
}

export function deleteV3Run(reportId: string): Promise<void> {
  return request<void>(`${PREFIX}/runs/${encodeURIComponent(reportId)}`, {
    method: "DELETE",
  });
}

/**
 * Build the URL for the HTML render endpoint. The caller decides
 * how to use it — open in a new tab, fetch + display in an iframe,
 * embed in a print preview, etc.
 */
export function v3HtmlUrl(reportId: string): string {
  return `${PREFIX}/runs/${encodeURIComponent(reportId)}/html`;
}

/**
 * Build the URL for the PDF render endpoint. Same as v3HtmlUrl.
 * Returns 503 when the server's BrowserLauncher isn't wired.
 */
export function v3PdfUrl(reportId: string): string {
  return `${PREFIX}/runs/${encodeURIComponent(reportId)}/pdf`;
}

/**
 * Build the URL for the native .docx endpoint. python-docx generates
 * a Word file from the persisted sections / charts / citations — no
 * Playwright dependency. Anchor + a target=_blank triggers the
 * browser's normal download flow.
 */
export function v3DocxUrl(reportId: string): string {
  return `${PREFIX}/runs/${encodeURIComponent(reportId)}/docx`;
}

// ---------------------------------------------------------------------------
// Streaming surface
// ---------------------------------------------------------------------------

/**
 * Fire-and-stream entrypoint. POST returns the new report_id
 * immediately; the engine runs in a background task. Connect to
 * ``v3EventsUrl(report_id)`` via EventSource to receive progress.
 */
export function startV3RunAsync(payload: V3StartPayload): Promise<V3StartAsyncResponse> {
  return request<V3StartAsyncResponse>(`${PREFIX}/runs/start`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Flip the server-side cancel token for an in-flight run. The
 * runner exits at the next safe point with partial work preserved
 * and a terminal ``run.cancelled`` event lands on the stream.
 *
 * Returns ``{cancelled: true}`` when the token was found.
 * ``{cancelled: false}`` is fine too — it means the run already
 * finished and there's nothing left to cancel.
 */
export function cancelV3Run(reportId: string): Promise<{ cancelled: boolean }> {
  return request<{ cancelled: boolean }>(
    `${PREFIX}/runs/${encodeURIComponent(reportId)}/cancel`,
    { method: "POST" },
  );
}

/**
 * Build the SSE URL for a v3 run. Pass to ``new EventSource(url)``.
 * The server keeps the connection open until the terminal event
 * lands, then closes. Late connectors (run already done) get a
 * single ``run.snapshot`` event before close.
 */
export function v3EventsUrl(reportId: string): string {
  return `${PREFIX}/runs/${encodeURIComponent(reportId)}/events`;
}

// ---------------------------------------------------------------------------
// Templates surface (PR3)
// ---------------------------------------------------------------------------

export function listV3Templates(): Promise<V3TemplateSummary[]> {
  return request<V3TemplateSummary[]>(`${PREFIX}/templates`);
}

export function uploadV3Template(
  payload: V3TemplateCreatePayload,
): Promise<V3TemplateSummary> {
  return request<V3TemplateSummary>(`${PREFIX}/templates`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function deleteV3Template(templateId: string): Promise<void> {
  return request<void>(
    `${PREFIX}/templates/${encodeURIComponent(templateId)}`,
    { method: "DELETE" },
  );
}

// ---------------------------------------------------------------------------
// Revisions surface (PR4)
// ---------------------------------------------------------------------------

export function startV3Revision(
  reportId: string,
  payload: { request: string },
): Promise<V3RevisionStartResponse> {
  return request<V3RevisionStartResponse>(
    `${PREFIX}/runs/${encodeURIComponent(reportId)}/revise`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

export function listV3Revisions(reportId: string): Promise<V3Revision[]> {
  return request<V3Revision[]>(
    `${PREFIX}/runs/${encodeURIComponent(reportId)}/revisions`,
  );
}

export function cancelV3Revision(
  revisionId: string,
): Promise<{ cancelled: boolean }> {
  return request<{ cancelled: boolean }>(
    `${PREFIX}/revisions/${encodeURIComponent(revisionId)}/cancel`,
    { method: "POST" },
  );
}

/**
 * SSE URL for a v3 revision. Same event shape as v3 runs (the
 * BrokerEmitter publishes against the revision_id), so
 * ``useV3RunStream`` could be reused — but a dedicated
 * ``useV3RevisionStream`` keeps the revision-specific terminal
 * handling (status flip from "running" → "completed" on the parent
 * report) cohesive.
 */
export function v3RevisionEventsUrl(revisionId: string): string {
  return `${PREFIX}/revisions/${encodeURIComponent(revisionId)}/events`;
}
