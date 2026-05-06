import { fetchJson } from "./client";

export type ReportLength = "concise" | "normal" | "elaborative";

export interface TopicEntry {
  topic: string;
  notes: string;
}

export interface CustomSection {
  id: string;
  title: string;
  description: string;
}

export interface MbConfig {
  report_length: ReportLength;
  enabled_section_ids: string[];
  section_topics: Record<string, TopicEntry[]>;
  custom_sections: CustomSection[];
  reference_portfolio: boolean;
}

export interface MbSchedule {
  id: string;
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
  is_enabled: boolean;
}

export type MbScheduleUpsert = Omit<MbSchedule, "id" | "is_enabled">;

export interface RecentReport {
  id: string;
  title: string;
  report_type: string;
  created_at: string;
}

export interface RecentReportsListResponse {
  reports: RecentReport[];
}

const BASE = "/api/departments/morning-briefing";

export const fetchConfig = (): Promise<MbConfig> =>
  fetchJson<MbConfig>(`${BASE}/config`);

export const updateConfig = (cfg: MbConfig): Promise<MbConfig> =>
  fetchJson<MbConfig>(`${BASE}/config`, { method: "PUT", json: cfg });

export const fetchSchedule = (): Promise<{ schedule: MbSchedule | null }> =>
  fetchJson<{ schedule: MbSchedule | null }>(`${BASE}/schedule`);

export const upsertSchedule = (payload: MbScheduleUpsert): Promise<MbSchedule> =>
  fetchJson<MbSchedule>(`${BASE}/schedule`, { method: "PUT", json: payload });

export const deleteSchedule = (): Promise<void> =>
  fetchJson<void>(`${BASE}/schedule`, { method: "DELETE" }).then(() => undefined);

export const fetchReports = async (): Promise<RecentReportsListResponse> => {
  const { items } = await fetchJson<{ items: RecentReport[] }>(
    `/api/reports?department=morning_briefing`,
  );
  return { reports: items };
};
