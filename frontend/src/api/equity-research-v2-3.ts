/**
 * v2.3 equity-research run-lifecycle client.
 *
 * Matches the three plain-JSON endpoints exposed by
 * `packages/server/.../routes/departments/equity_research_v2_3.py`:
 *
 *   POST /api/departments/equity-research/v2.3/runs
 *   POST /api/departments/equity-research/v2.3/runs/{run_id}/answer
 *   GET  /api/departments/equity-research/v2.3/runs/{run_id}
 *
 * No SSE on this surface yet — runs return synchronously with the
 * suspendable CLARIFY state inline. The composer polls `getV23Run`
 * to surface progress while the run advances.
 */
import { request } from "./_request";

export type V23Language = "en" | "zh-TW";

// Built-in report templates surfaced to the user as the "Template" picker.
// User-uploaded custom templates live alongside these (handled separately by
// the templates API and resolved server-side to a section plan); from the
// engine's perspective the run still carries a built-in report_type because
// the section plan baked into a custom template is materialized into outline
// sections at PLAN time.
export type V23ReportType =
  | "initiation"
  | "update"
  | "sector_research";

export type V23ReportLength = "concise" | "normal" | "elaborative";

// Server-side enum is `ReasoningEffort` with members MEDIUM and HIGH;
// "off" is represented by sending `null` (or omitting the field).
export type V23ReasoningEffort = "medium" | "high";

export type V23RunStatus =
  | "running"
  | "waiting_on_user"
  | "complete"
  | "failed";

export type V23Stage =
  | "clarify"
  | "plan"
  | "research"
  | "compute"
  | "synthesize"
  | "write"
  | "visualize"
  | "verify";

export interface V23ClarifyQuestion {
  id: string;
  question: string;
  why_blocking: string;
  default: string;
}

export interface V23ClarifyResult {
  outcome: "proceed" | "needs_input";
  assumptions: string[];
  questions: V23ClarifyQuestion[];
}

export interface V23RunState {
  run_id: string;
  status: V23RunStatus;
  current_stage: V23Stage | null;
  pending_questions: V23ClarifyQuestion[];
  clarify_result: V23ClarifyResult | null;
  last_error: string | null;
  retry_count: number;
  // Echoed so a reattached run can still render the user's original
  // request (UserBubble) without an extra round trip to /runs.
  raw_prompt: string;
  tickers: string[];
  report_type: V23ReportType;
  length: V23ReportLength;
  language: V23Language;
  // UUID of the custom template this run was started with, or null
  // when a built-in template (report_type) was used.
  template_id: string | null;
}

export interface V23StartRunPayload {
  raw_prompt: string;
  language?: V23Language;
  report_type?: V23ReportType;
  length?: V23ReportLength;
  /** When set, must be a UUID from the /api/report-templates collection.
   *  Picks a custom template; report_type then describes the closest
   *  built-in shape for compatibility (e.g. the server uses it for the
   *  default valuation_plan when the custom template doesn't specify). */
  template_id?: string | null;
  /** Optional: omit (or pass []) to let CLARIFY infer the subject
   *  ticker from `raw_prompt`. The single-textarea composer uses this
   *  path. The two-field v2.2-style composer (still used by the
   *  initial chat-follow-up shim) supplies tickers explicitly. */
  tickers?: string[];
  /** Extended-thinking effort. Omit (or pass null) for thinking off.
   *  The v2.3 wiring layer applies the directive only to PLAN +
   *  SYNTHESIZE stages and grows their `max_tokens` ceiling to absorb
   *  the thinking budget. */
  reasoning_effort?: V23ReasoningEffort | null;
}

export function startV23Run(payload: V23StartRunPayload): Promise<V23RunState> {
  return request<V23RunState>("/api/departments/equity-research/v2.3/runs", {
    method: "POST",
    body: JSON.stringify({
      language: "en",
      report_type: "initiation",
      length: "normal",
      ...payload,
    }),
  });
}

export function answerV23Run(
  runId: string,
  answers: Record<string, string>,
): Promise<V23RunState> {
  return request<V23RunState>(
    `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}/answer`,
    {
      method: "POST",
      body: JSON.stringify({ answers }),
    },
  );
}

export function getV23Run(runId: string): Promise<V23RunState> {
  return request<V23RunState>(
    `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}`,
  );
}


// ---------------------------------------------------------------------------
// Repository surface — list / delete / docx download
// ---------------------------------------------------------------------------

export interface V23RunSummary {
  run_id: string;
  status: V23RunStatus;
  tickers: string[];
  raw_prompt: string;
  report_type: V23ReportType;
  length: V23ReportLength;
  language: V23Language;
  created_at: string;
  updated_at: string;
}

export function listV23Runs(opts?: {
  status?: V23RunStatus;
  limit?: number;
}): Promise<V23RunSummary[]> {
  const params = new URLSearchParams();
  if (opts?.status) params.set("status", opts.status);
  if (opts?.limit !== undefined) params.set("limit", String(opts.limit));
  const qs = params.toString();
  const url = `/api/departments/equity-research/v2.3/runs${qs ? `?${qs}` : ""}`;
  return request<V23RunSummary[]>(url);
}

export function deleteV23Run(runId: string): Promise<void> {
  return request<void>(
    `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}`,
    { method: "DELETE" },
  );
}

/** Returns a URL the browser can navigate to in order to download the docx.
 *  The browser session cookie is sent automatically.
 */
export function v23DocxUrl(runId: string): string {
  return `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}/docx`;
}


// ---------------------------------------------------------------------------
// Structured payload — the source of truth the browser renderer consumes.
//
// `<V23ReportView>` plots this with inline-SVG charts (recharts). The same
// payload backs the .docx renderer on the server side; both are independent
// renderings of one structure (no docx -> browser parse, no drift).
// ---------------------------------------------------------------------------

export type V23ChartType =
  | "column"
  | "bar"
  | "line"
  | "area"
  | "pie"
  | "scatter"
  | "heatmap"
  | "table";

export interface V23BundleSeriesPoint {
  period: string;
  value: number;
}

export interface V23BundleFact {
  id: string;
  label: string;
  /** Scalar value (number / string) or a time-series (list of points). */
  value: number | string | V23BundleSeriesPoint[];
  unit: string | null;
  ticker: string | null;
}

export interface V23ChartSeries {
  name: string;
  value_fact_ids: string[];
}

export interface V23ChartSpec {
  id: string;
  section_id: string;
  claim: string;
  chart_type: V23ChartType;
  title: string;
  category_labels: string[];
  series: V23ChartSeries[];
  x_axis_label: string | null;
  y_axis_label: string | null;
}

export interface V23CanonicalFigure {
  fact_id: string;
  display: string;
}

export interface V23OutlineSection {
  id: string;
  title: string;
}

export interface V23ThesisPayload {
  language: V23Language;
  central_argument: string;
  key_takeaways: string[];
  valuation_stance: string;
  canonical_figures: V23CanonicalFigure[];
}

export interface V23LaneCoverage {
  total: number;
  satisfied: number;
  pct: number;
}

/** @deprecated Use V23LaneCoverage. Kept as an alias while consumers migrate. */
export type V23NarrativeCoverage = V23LaneCoverage;

export interface V23RunPayload {
  run_id: string;
  tickers: string[];
  report_type: V23ReportType;
  language: V23Language;
  thesis: V23ThesisPayload;
  sections: V23OutlineSection[];
  /** Resolved prose; still carries `[^N]` and `{{FIG:id}}` markers. */
  section_bodies: Record<string, string>;
  footnotes: string[];
  charts: V23ChartSpec[];
  figure_labels: Record<string, number>;
  bundle_facts: Record<string, V23BundleFact>;
  /** How many of the planner's `data_fact_ids` needs landed at least
   *  one EODHD-sourced fact. Null when the outline has no data-lane
   *  needs (N/A, not zero). */
  data_coverage?: V23LaneCoverage | null;
  /** How many of the planner's `web_fact_ids` needs landed at least
   *  one web_search-sourced fact. Null when the outline has no
   *  web-lane needs (N/A, not zero). */
  web_coverage?: V23LaneCoverage | null;
  /** Back-compat alias: mirrors `web_coverage`. New consumers should
   *  read `web_coverage` directly. */
  narrative_coverage: V23LaneCoverage | null;
}

export function getV23RunPayload(runId: string): Promise<V23RunPayload> {
  return request<V23RunPayload>(
    `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}/payload`,
  );
}


// ---------------------------------------------------------------------------
// SSE streaming
// ---------------------------------------------------------------------------

export interface V23StageStartedEvent {
  event: "stage_started";
  data: { slot: V23Stage };
}

export interface V23StageCompletedEvent {
  event: "stage_completed";
  data: { slot: V23Stage; retry_count: number };
}

export interface V23SuspendedEvent {
  event: "suspended";
  data: { slot: V23Stage; questions: V23ClarifyQuestion[] };
}

export interface V23FailedEvent {
  event: "failed";
  data: { slot: V23Stage | null; error: string; status?: number };
}

export interface V23CompletedEvent {
  event: "completed";
  data: Record<string, never>;
}

export interface V23StateEvent {
  event: "state";
  data: V23RunState;
}

export type V23StreamEvent =
  | V23StageStartedEvent
  | V23StageCompletedEvent
  | V23SuspendedEvent
  | V23FailedEvent
  | V23CompletedEvent
  | V23StateEvent;

export interface V23StreamHandlers {
  onEvent?: (event: V23StreamEvent) => void;
  onError?: (err: Error) => void;
}

/**
 * Open a streaming POST to one of the v2.3 SSE endpoints and forward
 * parsed events to ``handlers.onEvent``. Returns an AbortController so
 * the caller can cancel the connection (e.g. component unmount).
 *
 * EventSource only supports GET, so we use fetch + a manual SSE parser
 * over the ReadableStream body. This keeps the wire-level contract on
 * the server side: POST with JSON body, response is text/event-stream.
 */
function openSseStream(
  url: string,
  body: object,
  handlers: V23StreamHandlers,
): AbortController {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(body),
        credentials: "include",
        signal: controller.signal,
      });
      if (!resp.ok || resp.body === null) {
        handlers.onError?.(new Error(`Stream open failed: HTTP ${resp.status}`));
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        // SSE separates records with a blank line.
        let idx: number;
        while ((idx = buffer.indexOf("\n\n")) !== -1) {
          const chunk = buffer.slice(0, idx);
          buffer = buffer.slice(idx + 2);
          const evt = _parseSseChunk(chunk);
          if (evt !== null) handlers.onEvent?.(evt);
        }
      }
      // Flush any trailing record.
      if (buffer.trim().length > 0) {
        const evt = _parseSseChunk(buffer);
        if (evt !== null) handlers.onEvent?.(evt);
      }
    } catch (err) {
      if (controller.signal.aborted) return;
      handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
    }
  })();
  return controller;
}

function _parseSseChunk(chunk: string): V23StreamEvent | null {
  let event: string | null = null;
  let data: string | null = null;
  for (const line of chunk.split("\n")) {
    if (line.startsWith("event: ")) event = line.slice(7).trim();
    else if (line.startsWith("data: ")) data = line.slice(6);
  }
  if (event === null || data === null) return null;
  try {
    return { event, data: JSON.parse(data) } as V23StreamEvent;
  } catch {
    return null;
  }
}

export function streamV23Run(
  payload: V23StartRunPayload,
  handlers: V23StreamHandlers,
): AbortController {
  return openSseStream(
    "/api/departments/equity-research/v2.3/runs/stream",
    {
      language: "en",
      report_type: "initiation",
      length: "normal",
      ...payload,
    },
    handlers,
  );
}

export function streamV23Answer(
  runId: string,
  answers: Record<string, string>,
  handlers: V23StreamHandlers,
): AbortController {
  return openSseStream(
    `/api/departments/equity-research/v2.3/runs/${encodeURIComponent(runId)}/answer/stream`,
    { answers },
    handlers,
  );
}
