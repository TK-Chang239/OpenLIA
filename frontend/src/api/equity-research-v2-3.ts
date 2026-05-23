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
