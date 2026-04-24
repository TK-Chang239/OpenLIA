import { fetchJson } from "./client";

export type ReleaseTiming = "pre_market" | "post_market" | null;

export interface WatchlistEntry {
  id: string;
  ticker: string;
  company_name: string;
  next_earnings_date: string | null;
  release_timing: ReleaseTiming;
}

export interface WatchlistListResponse {
  entries: WatchlistEntry[];
}

export interface CustomSection {
  id: string;
  title: string;
  description: string;
}

export type ReportLength = "concise" | "normal" | "elaborative";

export interface EuConfig {
  report_length: ReportLength;
  enabled_section_ids: string[];
  custom_sections: CustomSection[];
}

export interface EuSchedule {
  id: string;
  user_id: string;
  time: string;
  timezone: string;
  days_of_week: number[];
  label: string | null;
  is_enabled: boolean;
  created_at: string;
  last_run_at: string | null;
}

export type EuScheduleCreate = Omit<
  EuSchedule,
  "id" | "user_id" | "created_at" | "last_run_at"
>;

export type EuScheduleUpdate = EuScheduleCreate;

export interface EuScheduleListResponse {
  schedules: EuSchedule[];
}

export interface RecentReport {
  id: string;
  title: string;
  subject: string | null;
  report_type: string;
  created_at: string;
}

export interface RecentReportsListResponse {
  reports: RecentReport[];
}

const BASE = "/api/departments/earnings-update";
const WATCHLIST_PATH = `${BASE}/watchlist`;
const CONFIG_PATH = `${BASE}/config`;
const SCHEDULES_PATH = `${BASE}/schedules`;
const REPORT_PATH = `${BASE}/report`;
const REPORTS_PATH = `${BASE}/reports`;

// ----- Watchlist -----

export async function fetchWatchlist(): Promise<WatchlistListResponse> {
  return fetchJson<WatchlistListResponse>(WATCHLIST_PATH);
}

export async function addWatchlistEntry(
  ticker: string,
): Promise<WatchlistEntry> {
  return fetchJson<WatchlistEntry>(WATCHLIST_PATH, {
    method: "POST",
    json: { ticker },
  });
}

export async function removeWatchlistEntry(entryId: string): Promise<void> {
  await fetchJson<null>(`${WATCHLIST_PATH}/${entryId}`, { method: "DELETE" });
}

// ----- Config -----

export async function fetchConfig(): Promise<EuConfig> {
  return fetchJson<EuConfig>(CONFIG_PATH);
}

export async function updateConfig(cfg: EuConfig): Promise<EuConfig> {
  return fetchJson<EuConfig>(CONFIG_PATH, { method: "PUT", json: cfg });
}

// ----- Schedules -----

export async function fetchSchedules(): Promise<EuScheduleListResponse> {
  const list = await fetchJson<EuSchedule[]>(SCHEDULES_PATH);
  return { schedules: list };
}

export async function createSchedule(
  payload: EuScheduleCreate,
): Promise<EuSchedule> {
  return fetchJson<EuSchedule>(SCHEDULES_PATH, {
    method: "POST",
    json: payload,
  });
}

export async function updateSchedule(
  id: string,
  payload: EuScheduleUpdate,
): Promise<EuSchedule> {
  return fetchJson<EuSchedule>(`${SCHEDULES_PATH}/${id}`, {
    method: "PATCH",
    json: payload,
  });
}

export async function deleteSchedule(id: string): Promise<void> {
  await fetchJson<unknown>(`${SCHEDULES_PATH}/${id}`, { method: "DELETE" });
}

// ----- Reports -----

export async function fetchRecentReports(
  limit = 5,
): Promise<RecentReportsListResponse> {
  return fetchJson<RecentReportsListResponse>(
    `${REPORTS_PATH}?limit=${limit}`,
  );
}

export function reportStreamUrl(): string {
  return REPORT_PATH;
}
