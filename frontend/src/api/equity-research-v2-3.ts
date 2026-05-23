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

export type V23ReportType =
  | "initiation"
  | "update"
  | "morning_brief"
  | "earnings_review";

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
}

export interface V23StartRunPayload {
  raw_prompt: string;
  language?: V23Language;
  report_type?: V23ReportType;
  tickers: string[];
}

export function startV23Run(payload: V23StartRunPayload): Promise<V23RunState> {
  return request<V23RunState>("/api/departments/equity-research/v2.3/runs", {
    method: "POST",
    body: JSON.stringify({
      language: "en",
      report_type: "initiation",
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
    { language: "en", report_type: "initiation", ...payload },
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
