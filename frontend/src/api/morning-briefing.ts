import { ApiError, fetchJson } from "./client";

const BASE = "/api/departments/morning-briefing";

function resolveUrl(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";
  if (!base) return path;
  const trimmedBase = base.replace(/\/+$/, "");
  const trimmedPath = path.startsWith("/") ? path : `/${path}`;
  return `${trimmedBase}${trimmedPath}`;
}

// ----- Types -----

export type MbReportLength = "concise" | "normal" | "elaborative";
export type MbReasoningEffort = "medium" | "high" | null;
export type MbRunStatus = "running" | "completed" | "failed" | "cancelled";
export type MbDayOfWeek = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export interface MbEnabledConnectors {
  provider_ids: string[];
  web_search: boolean;
}

/** Matches ScheduleOut from the route. */
export interface MbSchedule {
  id: string;
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
  is_enabled: boolean;
  template_id: string | null;
  instructions_id: string | null;
  enabled_connectors: Record<string, unknown>;
  provider_kind: string | null;
  model: string | null;
  language: string;
  length: string;
  reasoning_effort: string | null;
  web_search: boolean;
}

/** Matches ScheduleIn from the route. */
export interface MbScheduleIn {
  time: string;
  timezone: string;
  days_of_week: MbDayOfWeek[];
  label?: string;
  template_id?: string | null;
  instructions_id?: string | null;
  enabled_connectors?: MbEnabledConnectors;
  provider_kind?: string | null;
  model?: string | null;
  language?: string;
  length?: string;
  reasoning_effort?: string | null;
}

/** Matches TemplateOut from the route. */
export interface MbTemplate {
  id: string;
  name: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

/** Matches TemplateListOut from the route. */
export interface MbTemplateListResponse {
  templates: MbTemplate[];
}

/** Matches TemplateCreateIn from the route. */
export interface MbTemplateCreateIn {
  name: string;
  source_markdown: string;
}

/** Matches InstructionsOut from the route. */
export interface MbInstructions {
  id: string;
  name: string;
  is_builtin: boolean;
  created_at: string;
  updated_at: string;
}

/** Matches DataSourceOut from the route. */
export interface MbDataSource {
  key: string;
  display_name: string;
  category: string;
  routing: string;
  available: boolean;
  enabled: boolean;
  unavailable_reason: string | null;
}

/** Matches DataSourcesOut from the route. */
export interface MbDataSourcesResponse {
  sources: MbDataSource[];
}

/** Matches RunStartIn from the route. */
export interface MbRunStartIn {
  schedule_id?: string | null;
  template_id?: string;
  instructions_id?: string | null;
  enabled_connectors?: MbEnabledConnectors;
  provider_kind?: string;
  model?: string;
  language?: string;
  length?: string;
  reasoning_effort?: string | null;
}

export interface MbCoverMetric {
  label: string;
  value: string;
  change: string | null;
  tone: string | null;
}

export interface MbCardHighlights {
  subtitle: string | null;
  rating: string | null;
  metrics: MbCoverMetric[];
}

/** Matches RunSummaryOut from the route. */
export interface MbRunSummary {
  report_id: string;
  subject: string;
  trigger_kind: string;
  schedule_id: string | null;
  template_id: string;
  instructions_id: string | null;
  language: string;
  length: string;
  status: MbRunStatus;
  created_at: string;
  completed_at: string | null;
  reasoning_effort: string | null;
  highlights: MbCardHighlights | null;
}

export interface MbSectionRow {
  section_id: string;
  section_index: number;
  title: string;
  markdown: string;
  version: number;
}

export interface MbChartRow {
  chart_id: string;
  chart_type: string;
  title: string;
  spec: Record<string, unknown>;
  rendered_url: string | null;
  version: number;
}

export interface MbCitationRow {
  source_id: string;
  tool_name: string;
  display_index: number | null;
  provenance: Record<string, unknown>;
}

export interface MbCoverSpec {
  subtitle?: string | null;
  tagline?: string | null;
  tldr?: string[];
  key_metrics?: MbCoverMetric[];
  rating?: string | null;
  upside_pct?: number | null;
}

/** Matches RunDetailOut from the route. */
export interface MbRunDetail {
  report: MbRunSummary;
  error_message: string | null;
  sections: MbSectionRow[];
  charts: MbChartRow[];
  citations: MbCitationRow[];
  cover: MbCoverSpec | null;
}

// ----- SSE event types -----

export type MbEventType =
  | "run.started"
  | "tool.called"
  | "tool.completed"
  | "section.written"
  | "chart.emitted"
  | "run.completed"
  | "run.failed"
  | "run.cancelled"
  | "run.snapshot";

export interface MbEvent {
  type: MbEventType;
  payload: Record<string, unknown>;
}

export const MB_TERMINAL_EVENT_TYPES: ReadonlySet<MbEventType> =
  new Set<MbEventType>([
    "run.completed",
    "run.failed",
    "run.cancelled",
    "run.snapshot",
  ]);

// ----- Schedules -----

export async function listMbSchedules(): Promise<MbSchedule[]> {
  return fetchJson<MbSchedule[]>(`${BASE}/schedules`);
}

export async function createMbSchedule(
  payload: MbScheduleIn,
): Promise<MbSchedule> {
  return fetchJson<MbSchedule>(`${BASE}/schedules`, {
    method: "POST",
    json: payload,
  });
}

export async function updateMbSchedule(
  id: string,
  payload: MbScheduleIn,
): Promise<MbSchedule> {
  return fetchJson<MbSchedule>(`${BASE}/schedules/${encodeURIComponent(id)}`, {
    method: "PATCH",
    json: payload,
  });
}

export async function deleteMbSchedule(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/schedules/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ----- Templates -----

export async function listMbTemplates(): Promise<MbTemplateListResponse> {
  return fetchJson<MbTemplateListResponse>(`${BASE}/templates`);
}

/** Create a template from a JSON markdown body. */
export async function createMbTemplate(
  payload: MbTemplateCreateIn,
): Promise<MbTemplate> {
  return fetchJson<MbTemplate>(`${BASE}/templates`, {
    method: "POST",
    json: payload,
  });
}

/**
 * Upload a template from a document file (multipart). The browser sets the
 * multipart boundary automatically; do NOT set Content-Type here.
 */
export async function uploadMbTemplate(
  name: string,
  file: File,
): Promise<MbTemplate> {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", file, file.name);
  let res: Response;
  try {
    res = await fetch(resolveUrl(`${BASE}/templates`), {
      method: "POST",
      credentials: "include",
      body: fd,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "network error";
    throw new ApiError(0, message);
  }
  const contentType = res.headers.get("Content-Type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await res.json().catch(() => null)
    : null;
  if (!res.ok) {
    throw new ApiError(
      res.status,
      `HTTP ${res.status} on template upload`,
      parsedBody,
    );
  }
  return parsedBody as MbTemplate;
}

export async function deleteMbTemplate(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/templates/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ----- Instructions -----

export async function listMbInstructions(): Promise<MbInstructions[]> {
  return fetchJson<MbInstructions[]>(`${BASE}/instructions`);
}

/**
 * Upload an instructions profile (multipart). The browser sets the multipart
 * boundary; do NOT set Content-Type here.
 */
export async function createMbInstructions(
  name: string,
  file: File,
): Promise<MbInstructions> {
  const fd = new FormData();
  fd.append("name", name);
  fd.append("file", file, file.name);
  let res: Response;
  try {
    res = await fetch(resolveUrl(`${BASE}/instructions`), {
      method: "POST",
      credentials: "include",
      body: fd,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "network error";
    throw new ApiError(0, message);
  }
  const contentType = res.headers.get("Content-Type") ?? "";
  const parsedBody = contentType.includes("application/json")
    ? await res.json().catch(() => null)
    : null;
  if (!res.ok) {
    throw new ApiError(
      res.status,
      `HTTP ${res.status} on instructions upload`,
      parsedBody,
    );
  }
  return parsedBody as MbInstructions;
}

export async function deleteMbInstructions(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/instructions/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

// ----- Data sources -----

export interface MbDataSourcesParams {
  provider_kind?: string;
  model?: string;
  enabled_provider_ids?: string[];
  web_search?: boolean;
  schedule_id?: string;
}

export async function getMbDataSources(
  params?: MbDataSourcesParams,
): Promise<MbDataSourcesResponse> {
  const q = new URLSearchParams();
  if (params?.provider_kind) q.set("provider_kind", params.provider_kind);
  if (params?.model) q.set("model", params.model);
  if (params?.enabled_provider_ids) {
    for (const id of params.enabled_provider_ids)
      q.append("enabled_provider_ids", id);
  }
  if (params?.web_search !== undefined)
    q.set("web_search", String(params.web_search));
  if (params?.schedule_id) q.set("schedule_id", params.schedule_id);
  const qs = q.toString();
  return fetchJson<MbDataSourcesResponse>(
    `${BASE}/data-sources${qs ? `?${qs}` : ""}`,
  );
}

// ----- Runs -----

export async function startMbRun(
  payload: MbRunStartIn,
): Promise<{ report_id: string }> {
  return fetchJson<{ report_id: string }>(`${BASE}/runs/start`, {
    method: "POST",
    json: payload,
  });
}

export async function listMbRuns(
  status?: MbRunStatus,
): Promise<MbRunSummary[]> {
  const qs = status ? `?status=${encodeURIComponent(status)}` : "";
  return fetchJson<MbRunSummary[]>(`${BASE}/runs${qs}`);
}

export async function getMbRun(id: string): Promise<MbRunDetail> {
  return fetchJson<MbRunDetail>(`${BASE}/runs/${encodeURIComponent(id)}`);
}

export async function deleteMbRun(id: string): Promise<void> {
  await fetchJson<null>(`${BASE}/runs/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function cancelMbRun(id: string): Promise<{ cancelled: boolean }> {
  return fetchJson<{ cancelled: boolean }>(
    `${BASE}/runs/${encodeURIComponent(id)}/cancel`,
    {
      method: "POST",
    },
  );
}

export function mbRunEventsUrl(id: string): string {
  return `${BASE}/runs/${encodeURIComponent(id)}/events`;
}

export function mbRunDownloadUrl(
  id: string,
  fmt: "html" | "pdf" | "docx",
): string {
  return `${BASE}/runs/${encodeURIComponent(id)}/${fmt}`;
}
