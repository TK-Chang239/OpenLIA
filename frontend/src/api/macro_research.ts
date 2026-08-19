export interface DashboardSummary {
  slug: string;
  display_name: string;
  /** ISO timestamp of the framework's last generated cache row; null when
   * never generated. */
  generated_at?: string | null;
  /** True when never generated or older than the framework's TTL. */
  is_stale?: boolean;
}

export interface DashboardResponse<T = unknown> {
  payload: T | null;
  generated_at: string | null;
  is_stale: boolean;
  provenance: string | null;
}

export interface ScheduleState {
  cron_expression: string | null;
  last_assessment_at?: string | null;
}

const base = "/api/departments/macro_research";

async function _fetch(url: string, init: RequestInit = {}): Promise<unknown> {
  const r = await fetch(url, { credentials: "include", ...init });
  if (!r.ok) {
    throw new Error(`${init.method ?? "GET"} ${url} failed: ${r.status}`);
  }
  return r.status === 204 ? null : r.json();
}

export function listDashboards(): Promise<{ dashboards: DashboardSummary[] }> {
  return _fetch(`${base}/dashboards`) as Promise<{ dashboards: DashboardSummary[] }>;
}

export function getDashboard<T = unknown>(
  slug: string,
): Promise<DashboardResponse<T>> {
  return _fetch(`${base}/dashboards/${slug}`) as Promise<DashboardResponse<T>>;
}

export interface RunAssessmentResult {
  job_run_id: string | null;
  status: string;
}

export async function runAssessment(slug: string): Promise<RunAssessmentResult> {
  const url = `${base}/dashboards/${slug}/refresh`;
  const r = await fetch(url, { method: "POST", credentials: "include" });
  // 409 means a run for this dashboard is already in flight — not an error.
  // The caller should keep polling for the in-progress result.
  if (r.status === 409) {
    return { job_run_id: null, status: "already_running" };
  }
  if (!r.ok) {
    throw new Error(`POST ${url} failed: ${r.status}`);
  }
  return r.json() as Promise<RunAssessmentResult>;
}

export function getSchedule(): Promise<ScheduleState> {
  return _fetch(`${base}/schedule`) as Promise<ScheduleState>;
}

export function putSchedule(cron_expression: string): Promise<ScheduleState> {
  return _fetch(`${base}/schedule`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cron_expression }),
  }) as Promise<ScheduleState>;
}

export function deleteSchedule(): Promise<null> {
  return _fetch(`${base}/schedule`, { method: "DELETE" }) as Promise<null>;
}
