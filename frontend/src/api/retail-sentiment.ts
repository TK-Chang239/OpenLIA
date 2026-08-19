import { fetchJson } from "./client";

const BASE = "/api/departments/retail_sentiment";

async function _fetch(url: string, init: RequestInit = {}): Promise<unknown> {
  const r = await fetch(url, { credentials: "include", ...init });
  if (!r.ok) {
    throw new Error(`${init.method ?? "GET"} ${url} failed: ${r.status}`);
  }
  return r.status === 204 ? null : r.json();
}

// ---------------------------------------------------------------------------
// Payload types
// ---------------------------------------------------------------------------

export interface RsSignal {
  name: string;
  severity: "info" | "caution" | "alert";
  note: string;
}

export interface RsEvidenceItem {
  title: string;
  url: string;
  source: string;
  classification: "bullish" | "bearish" | "neutral";
  published_at?: string | null;
}

export interface RetailSentimentPayload {
  subject: string;
  sentiment_score: number; // -1..1
  direction: "bullish" | "bearish" | "neutral";
  momentum: number | null;
  trend_label: string | null;
  buzz_level: "low" | "elevated" | "high";
  buzz_note: string;
  bull_pct: number; // 0..100
  bear_pct: number; // 0..100
  narratives: string[];
  signals: RsSignal[];
  evidence: RsEvidenceItem[];
  narrative: string;
  aggregated_sentiment: number | null;
  analyst_gap: number | null;
  captured_at: string | null;
  /** Run's citation ledger: resolves [^source_id] markers in the narrative. */
  citations?: { source_id: string; title?: string | null; url?: string | null }[];
}

export interface DashboardResponse<T = unknown> {
  payload: T | null;
  generated_at: string | null;
  is_stale: boolean;
  provenance: string | null;
}

export interface DashboardConfig {
  view_config: Record<string, unknown>;
  threshold_overrides: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Schedule types (unchanged from prior shape)
// ---------------------------------------------------------------------------

export interface RsSchedule {
  id: string;
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
  is_enabled: boolean;
}

export interface RsScheduleUpsert {
  time: string;
  timezone: string;
  days_of_week: string[];
  label: string;
  is_enabled?: boolean;
}

// ---------------------------------------------------------------------------
// Dashboard API
// ---------------------------------------------------------------------------

export function getDashboard(
  ticker: string,
): Promise<DashboardResponse<RetailSentimentPayload>> {
  return _fetch(
    `${BASE}/dashboard/${encodeURIComponent(ticker)}`,
  ) as Promise<DashboardResponse<RetailSentimentPayload>>;
}

export function getHistory(
  ticker: string,
  days = 7,
): Promise<Array<{ payload: RetailSentimentPayload; generated_at: string }>> {
  return _fetch(
    `${BASE}/dashboard/${encodeURIComponent(ticker)}/history?days=${days}`,
  ) as Promise<Array<{ payload: RetailSentimentPayload; generated_at: string }>>;
}

export interface RefreshResult {
  job_run_id: string | null;
  status: string;
}

export async function refreshDashboard(ticker: string): Promise<RefreshResult> {
  const url = `${BASE}/dashboard/${encodeURIComponent(ticker)}/refresh`;
  const r = await fetch(url, { method: "POST", credentials: "include" });
  if (r.status === 409) {
    return { job_run_id: null, status: "already_running" };
  }
  if (!r.ok) {
    throw new Error(`POST ${url} failed: ${r.status}`);
  }
  return r.json() as Promise<RefreshResult>;
}

// ---------------------------------------------------------------------------
// Config API
// ---------------------------------------------------------------------------

export function getConfig(): Promise<DashboardConfig> {
  return _fetch(`${BASE}/config`) as Promise<DashboardConfig>;
}

export function putConfig(body: Partial<DashboardConfig>): Promise<DashboardConfig> {
  return _fetch(`${BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }) as Promise<DashboardConfig>;
}

// ---------------------------------------------------------------------------
// Schedule API (preserved from prior shape)
// ---------------------------------------------------------------------------

export function getSchedule(): Promise<{ schedule: RsSchedule | null }> {
  return fetchJson(`${BASE}/schedule`);
}

export function putSchedule(payload: RsScheduleUpsert): Promise<RsSchedule> {
  return fetchJson<RsSchedule>(`${BASE}/schedule`, {
    method: "PUT",
    json: payload,
  });
}
