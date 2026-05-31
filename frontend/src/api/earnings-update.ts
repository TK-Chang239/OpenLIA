import { fetchJson } from "./client";

const BASE = "/api/departments/earnings-update/v2";

// ----- Types -----

export type ReportLength = "concise" | "normal" | "elaborative";
export type ReleaseTiming = "pre_market" | "post_market" | null;
export type ReasoningEffort = "medium" | "high" | null;
export type RunStatus = "running" | "completed" | "failed";
export type ScheduleStatus = "pending" | "reported" | "skipped";

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string | null;
  created_at: string;
}
export interface WatchlistListResponse {
  entries: WatchlistEntry[];
}

export interface EuSettings {
  provider_kind: string;
  model: string;
  template_id: string;
  language: string;
  length: ReportLength;
  reasoning_effort: ReasoningEffort;
  financial_enabled: boolean;
  calendar_enabled: boolean;
  web_search_enabled: boolean;
}

export interface DataSourceSlot {
  available: boolean;
  provider_label: string | null;
  unavailable_reason: string | null;
}
export interface OtherConnector {
  display_name: string;
  category: string;
}
export interface DataSourcesInfo {
  financial: DataSourceSlot;
  earnings_calendar: DataSourceSlot;
  web_search: DataSourceSlot;
  other_connectors: OtherConnector[];
}

export const getEuDataSources = (
  params?: { provider_kind?: string; model?: string },
): Promise<DataSourcesInfo> => {
  const q = new URLSearchParams();
  if (params?.provider_kind) q.set("provider_kind", params.provider_kind);
  if (params?.model) q.set("model", params.model);
  const qs = q.toString();
  return fetchJson<DataSourcesInfo>(`${BASE}/data-sources${qs ? `?${qs}` : ""}`);
};

// Backend TemplateOut includes updated_at; included here for completeness.
export interface EuTemplate {
  id: string;
  name: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}
export interface TemplateListResponse {
  templates: EuTemplate[];
}

// Backend ScheduleEntryOut includes eps_estimate, revenue_estimate, attempts.
export interface EuScheduleEntry {
  id: string;
  ticker: string;
  fiscal_date: string;
  release_timing: ReleaseTiming;
  eps_estimate: string | null;
  revenue_estimate: string | null;
  scheduled_run_at: string;
  status: ScheduleStatus;
  attempts: number;
  report_id: string | null;
}
export interface ScheduleListResponse {
  schedule: EuScheduleEntry[];
}

// Backend RunSummaryOut uses report_id (not id) as the primary key.
export interface RunSummary {
  report_id: string;
  ticker: string;
  subject: string;
  template_id: string;
  trigger_kind: "scheduled" | "on_demand";
  fiscal_date: string | null;
  language: string;
  length: string;
  status: RunStatus;
  created_at: string;
  completed_at: string | null;
  reasoning_effort: ReasoningEffort;
}

export interface SectionRow {
  section_id: string;
  section_index: number;
  title: string;
  markdown: string;
  version: number;
}
export interface ChartRow {
  chart_id: string;
  chart_type: string;
  title: string;
  spec: Record<string, unknown>;
  rendered_url: string | null;
  version: number;
}
export interface CitationRow {
  source_id: string;
  tool_name: string;
  display_index: number | null;
  provenance: Record<string, unknown>;
}

export interface CoverMetric {
  label: string;
  value: string;
  change: string | null;
  tone: string | null;
}
export interface CoverSpec {
  subtitle?: string | null;
  tagline?: string | null;
  tldr?: string[];
  key_metrics?: CoverMetric[];
  rating?: string | null;
  upside_pct?: number | null;
}

export interface RunDetail {
  report: RunSummary;
  error_message: string | null;
  sections: SectionRow[];
  charts: ChartRow[];
  citations: CitationRow[];
  cover: CoverSpec | null;
}

// ----- SSE event types -----

export type EuEventType =
  | "run.started"
  | "tool.called"
  | "tool.completed"
  | "section.written"
  | "chart.emitted"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "run.snapshot";

export interface EuEvent {
  type: EuEventType;
  payload: Record<string, unknown>;
}

export const EU_TERMINAL_EVENT_TYPES: ReadonlySet<EuEventType> = new Set<EuEventType>([
  "run.completed",
  "run.failed",
  "run.cancelled",
  "run.snapshot",
]);

// ----- Watchlist -----

export async function fetchWatchlist(): Promise<WatchlistListResponse> {
  return fetchJson<WatchlistListResponse>(`${BASE}/watchlist`);
}

export async function addWatchlistEntry(ticker: string): Promise<WatchlistEntry> {
  return fetchJson<WatchlistEntry>(`${BASE}/watchlist`, {
    method: "POST",
    json: { ticker },
  });
}

export async function removeWatchlistEntry(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/watchlist/${id}`, { method: "DELETE" });
}

export async function syncWatchlist(): Promise<{ synced: number }> {
  return fetchJson<{ synced: number }>(`${BASE}/watchlist/sync`, {
    method: "POST",
  });
}

// ----- Settings -----

export async function fetchSettings(): Promise<EuSettings> {
  return fetchJson<EuSettings>(`${BASE}/settings`);
}

export async function updateSettings(next: EuSettings): Promise<EuSettings> {
  return fetchJson<EuSettings>(`${BASE}/settings`, {
    method: "PUT",
    json: next,
  });
}

// ----- Templates -----

export async function fetchTemplates(): Promise<TemplateListResponse> {
  return fetchJson<TemplateListResponse>(`${BASE}/templates`);
}

export async function uploadTemplate(payload: {
  name: string;
  source_markdown: string;
}): Promise<EuTemplate> {
  return fetchJson<EuTemplate>(`${BASE}/templates`, {
    method: "POST",
    json: payload,
  });
}

export async function deleteTemplate(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/templates/${id}`, { method: "DELETE" });
}

// ----- Schedule (read-only) -----

export async function fetchSchedule(): Promise<ScheduleListResponse> {
  return fetchJson<ScheduleListResponse>(`${BASE}/schedule`);
}

// ----- Runs -----

export async function startRun(payload: {
  ticker: string;
}): Promise<{ report_id: string }> {
  return fetchJson<{ report_id: string }>(`${BASE}/runs/start`, {
    method: "POST",
    json: payload,
  });
}

export async function fetchRuns(status?: RunStatus): Promise<RunSummary[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJson<RunSummary[]>(`${BASE}/runs${qs}`);
}

export async function getRun(id: string): Promise<RunDetail> {
  return fetchJson<RunDetail>(`${BASE}/runs/${encodeURIComponent(id)}`);
}

export async function deleteRun(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/runs/${id}`, { method: "DELETE" });
}

export async function cancelRun(id: string): Promise<{ cancelled: boolean }> {
  return fetchJson<{ cancelled: boolean }>(`${BASE}/runs/${id}/cancel`, {
    method: "POST",
  });
}

export function runEventsUrl(id: string): string {
  return `${BASE}/runs/${encodeURIComponent(id)}/events`;
}
