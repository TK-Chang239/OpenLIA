import { fetchJson } from "./client";

export type ResolutionMode = "catalog" | "manual_endpoint" | "websearch";

export type SmokeStatus =
  | "success"
  | "auth"
  | "bad_params"
  | "schema_miss"
  | "empty"
  | "transient";

export interface RunnerSpecRow {
  id: string;
  department_id: string;
  need_id: string;
  connector_id: string;
  access_mode: string;
  spec: Record<string, unknown>;
  canary_value: Record<string, unknown> | null;
  canary_at: string | null;
  resolution_mode?: ResolutionMode;
  user_inputs?: Record<string, unknown> | null;
  llm_warning?: string | null;
  manually_overridden?: boolean;
  last_smoke_at?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface SmokeFailure {
  status: SmokeStatus;
  attempts: number;
  error_class: string | null;
  error_message: string | null;
  response_excerpt: string | null;
}

export interface ResolveSaveRequest {
  department_id: string;
  need_id: string;
  connector_id: string;
  resolution_mode: "manual_endpoint" | "websearch";
  user_picked_endpoint: string;
  user_hint?: string | null;
  websearch_url?: string | null;
  manually_overridden?: boolean;
}

export interface ResolveSaveSuccess {
  ok: true;
  spec: RunnerSpecRow;
  warning: string | null;
}

export interface ResolveSaveFailure {
  ok: false;
  failure: SmokeFailure;
  warning: string | null;
}

export type ResolveSaveResult = ResolveSaveSuccess | ResolveSaveFailure;

export interface HistoryEntry {
  kind: "resolver" | "smoke";
  status: string;
  error_class: string | null;
  error_message: string | null;
  created_at: string;
  attempt?: number;
}

export const listRunnerSpecs = (departmentId?: string) => {
  const qs = departmentId
    ? `?department_id=${encodeURIComponent(departmentId)}`
    : "";
  return fetchJson<RunnerSpecRow[]>(`/api/runner-specs${qs}`);
};

export const resolveAndSaveSpec = (req: ResolveSaveRequest) =>
  fetchJson<ResolveSaveResult>("/api/runner-specs/resolve", {
    method: "POST",
    json: req,
  });

export const getSpecHistory = (specId: string) =>
  fetchJson<HistoryEntry[]>(
    `/api/runner-specs/${encodeURIComponent(specId)}/history`,
  );
