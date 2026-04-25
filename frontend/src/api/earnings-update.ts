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

export interface RecentReportsQuery {
  limit?: number;
  q?: string;
  ticker?: string;
  from?: string;
  to?: string;
}

export async function fetchRecentReports(
  query: number | RecentReportsQuery = 5,
): Promise<RecentReportsListResponse> {
  const opts: RecentReportsQuery =
    typeof query === "number" ? { limit: query } : query;
  const params = new URLSearchParams();
  params.set("limit", String(opts.limit ?? 5));
  if (opts.q) params.set("q", opts.q);
  if (opts.ticker) params.set("ticker", opts.ticker);
  if (opts.from) params.set("from", opts.from);
  if (opts.to) params.set("to", opts.to);
  return fetchJson<RecentReportsListResponse>(
    `${REPORTS_PATH}?${params.toString()}`,
  );
}

export async function deleteReport(reportId: string): Promise<void> {
  await fetchJson<unknown>(`${REPORTS_PATH}/${reportId}`, { method: "DELETE" });
}

export function reportStreamUrl(): string {
  return REPORT_PATH;
}

export interface OnDemandReportResult {
  report_id: string;
  title: string;
}

/**
 * POST to /report, consume the SSE stream, and resolve with
 * `{report_id, title}` once a `report.complete` event arrives. Rejects if the
 * stream ends without a complete event, or if a `report.error` event is
 * emitted.
 */
export async function startOnDemandReport(payload: {
  ticker: string;
}): Promise<OnDemandReportResult> {
  const res = await fetch(REPORT_PATH, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ ticker: payload.ticker }),
  });
  if (!res.ok || !res.body) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      if (body && typeof body === "object" && "detail" in body) {
        detail = String((body as { detail: unknown }).detail);
      }
    } catch {
      // ignore parse error
    }
    throw new Error(detail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let title = "";
  try {
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let nl = buffer.indexOf("\n\n");
      while (nl !== -1) {
        const chunk = buffer.slice(0, nl);
        buffer = buffer.slice(nl + 2);
        nl = buffer.indexOf("\n\n");

        const line = chunk.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const raw = line.slice("data: ".length);
        let event: { type?: string; [k: string]: unknown };
        try {
          event = JSON.parse(raw) as { type?: string; [k: string]: unknown };
        } catch {
          continue;
        }

        if (event.type === "report.start") {
          // schema title arrives with report.complete; no-op here
        } else if (event.type === "report.complete") {
          const schema = event.schema as { title?: string } | undefined;
          title = schema?.title ?? "Earnings Update";
          return {
            report_id: String(event.report_id),
            title,
          };
        } else if (event.type === "report.error") {
          throw new Error(String(event.message ?? "Report generation failed"));
        }
      }
    }
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }
  throw new Error("Report stream ended without a completion event");
}
