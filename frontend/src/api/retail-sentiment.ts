import { fetchJson } from "./client";

const BASE = "/api/departments/retail_sentiment";

export interface RsSnapshot {
  ticker: string;
  captured_at: string;
  sentiment_score: number;
  buzz_volume: number;
  sentiment_momentum: number;
  bull_bear_ratio: number;
  buzz_sentiment_divergence: number;
  social_velocity: number;
  cross_source_agreement: number;
  put_call_ratio: number | null;
  short_interest_pressure: number | null;
  narrative_concentration: number | null;
  institutional_retail_gap: number | null;
  event_sensitivity: number | null;
  source_breakdown: Record<string, number>;
}

export interface RsSpike {
  ticker: string;
  detected_at: string;
  buzz: number;
  baseline_mean: number;
  baseline_stddev: number;
  z_score: number;
}

export interface RsDashboard {
  tickers: string[];
  snapshots: RsSnapshot[];
  generated_at: string;
}

export interface RsConfig {
  id: string;
  user_id: string;
  active_tab: string;
  metric_settings: Record<string, unknown>;
  filter_presets: unknown[];
  refresh_interval_minutes: number;
}

export interface RsConfigUpdate {
  active_tab?: string;
  metric_settings?: Record<string, unknown>;
  filter_presets?: unknown[];
  refresh_interval_minutes?: number;
}

export interface RsRunResponse {
  snapshots: Array<RsSnapshot & { snapshot_id: string; spike: RsSpike | null }>;
}

export function getDashboard(): Promise<RsDashboard> {
  return fetchJson<RsDashboard>(`${BASE}/dashboard`);
}

export function getHistory(ticker: string, days = 7): Promise<{ ticker: string; snapshots: RsSnapshot[] }> {
  return fetchJson(`${BASE}/dashboard/history?ticker=${encodeURIComponent(ticker)}&days=${days}`);
}

export function getConfig(): Promise<RsConfig> {
  return fetchJson<RsConfig>(`${BASE}/config`);
}

export function updateConfig(payload: RsConfigUpdate): Promise<RsConfig> {
  return fetchJson<RsConfig>(`${BASE}/config`, { method: "PUT", json: payload });
}

export function runSnapshot(tickers: string[]): Promise<RsRunResponse> {
  return fetchJson<RsRunResponse>(`${BASE}/run`, { method: "POST", json: { tickers } });
}

export function getStockSentiment(ticker: string): Promise<{ latest: RsSnapshot; history: RsSnapshot[] }> {
  return fetchJson(`${BASE}/stocks/${encodeURIComponent(ticker)}/sentiment`);
}

export function getSpikes(): Promise<{ spikes: RsSpike[] }> {
  return fetchJson(`${BASE}/spikes`);
}
