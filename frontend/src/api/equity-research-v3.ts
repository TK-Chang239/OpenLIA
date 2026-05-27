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
  provider_kind: string;
  model: string;
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
}

export interface V3SectionRow {
  section_id: string;
  section_index: number;
  title: string;
  markdown: string;
}

export interface V3ChartRow {
  chart_id: string;
  chart_type: string;
  title: string;
  spec: Record<string, unknown>;
  rendered_url: string | null;
}

export interface V3CitationRow {
  source_id: string;
  tool_name: string;
  display_index: number | null;
  provenance: Record<string, unknown>;
}

export interface V3ReportDetail {
  report: V3ReportSummary;
  error_message: string | null;
  sections: V3SectionRow[];
  charts: V3ChartRow[];
  citations: V3CitationRow[];
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
