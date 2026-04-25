export interface DashboardSummary {
  slug: string;
  display_name: string;
}

export interface DashboardTier {
  tier: "T1" | "T2" | "T3" | "T4" | "T5";
  data: Record<string, unknown>;
  errors: string[];
  generated_at: string | null;
}

export interface DashboardResult {
  slug: string;
  display_name: string;
  severity: "green" | "amber" | "red" | "neutral";
  tiers: DashboardTier[];
  headline: string | null;
  generated_at: string;
  smart_mode_active: boolean;
}

export interface DashboardConfig {
  view_config: Record<string, unknown>;
  threshold_overrides: Record<string, unknown>;
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

export function getDashboard(
  slug: string,
  smartMode = false,
): Promise<DashboardResult> {
  const qs = smartMode ? "?smart_mode=true" : "";
  return _fetch(`${base}/dashboards/${slug}${qs}`) as Promise<DashboardResult>;
}

export function getConfig(slug: string): Promise<DashboardConfig> {
  return _fetch(`${base}/dashboards/${slug}/config`) as Promise<DashboardConfig>;
}

export function putConfig(
  slug: string,
  body: Partial<DashboardConfig>,
): Promise<DashboardConfig> {
  return _fetch(`${base}/dashboards/${slug}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }) as Promise<DashboardConfig>;
}

export function putThresholdOverrides(
  slug: string,
  threshold_overrides: Record<string, unknown>,
): Promise<DashboardConfig> {
  return _fetch(`${base}/dashboards/${slug}/threshold-overrides`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ threshold_overrides }),
  }) as Promise<DashboardConfig>;
}

export function runAssessment(
  slug: string,
): Promise<{ job_run_id: string; status: string }> {
  return _fetch(`${base}/dashboards/${slug}/assessment/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  }) as Promise<{ job_run_id: string; status: string }>;
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
