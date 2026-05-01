import { fetchJson } from "./client";

export interface RunnerSpecRow {
  id: string;
  department_id: string;
  need_id: string;
  connector_id: string;
  access_mode: string;
  spec: Record<string, unknown>;
  canary_value: Record<string, unknown> | null;
  canary_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export const listRunnerSpecs = (departmentId?: string) => {
  const qs = departmentId
    ? `?department_id=${encodeURIComponent(departmentId)}`
    : "";
  return fetchJson<RunnerSpecRow[]>(`/api/runner-specs${qs}`);
};
