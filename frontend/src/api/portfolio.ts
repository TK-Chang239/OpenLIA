/**
 * Portfolio API client — typed wrapper for /api/portfolio/*.
 *
 * Decimal fields travel as strings on the wire; callers are responsible
 * for formatting. Groups are derived from a JSON blob stored in `notes`
 * server-side; callers pass and receive `groups: string[]`.
 */

export interface PortfolioHolding {
  id: string;
  ticker: string;
  name: string | null;
  shares: string | null;
  cost_basis: string | null;
  currency: string;
  groups: string[];
  notes_text: string | null;
  added_at: string;
  updated_at: string;
}

export interface HoldingInput {
  ticker: string;
  shares?: string | null;
  cost_basis?: string | null;
  currency?: string;
  notes?: string | null;
  groups?: string[];
}

export interface HoldingPatch {
  shares?: string | null;
  cost_basis?: string | null;
  currency?: string;
  notes?: string | null;
  groups?: string[];
}

export interface PositionAnalytic {
  holding_id: string;
  ticker: string;
  shares: string | null;
  cost_basis: string | null;
  last_price: string | null;
  market_value: string | null;
  unrealized_pl: string | null;
  unrealized_pl_pct: string | null;
  weight: string | null;
  currency: string;
}

export interface AnalyticsResponse {
  total_market_value: string;
  total_cost_basis: string;
  total_unrealized_pl: string;
  total_unrealized_pl_pct: string | null;
  positions: PositionAnalytic[];
  allocations: Record<string, string>;
  last_quote_at?: string | null;
  display_currency?: string;
  currencies_present?: string[];
  needs_fx?: boolean;
  fx_unavailable?: boolean;
}

export interface CsvImportResponse {
  created: PortfolioHolding[];
  errors: { row: string; error: string }[];
}

export interface RefreshPricesResponse {
  prices: Record<string, string | null>;
}

export interface SearchResult {
  ticker: string;
  name: string | null;
  exchange?: string | null;
  already_added?: boolean;
}

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

export async function fetchHoldings(): Promise<PortfolioHolding[]> {
  const res = await fetch("/api/portfolio/holdings", { credentials: "include" });
  return jsonOrThrow<PortfolioHolding[]>(res);
}

export async function createHolding(
  input: HoldingInput,
): Promise<PortfolioHolding> {
  const res = await fetch("/api/portfolio/holdings", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  return jsonOrThrow<PortfolioHolding>(res);
}

export async function updateHolding(
  id: string,
  patch: HoldingPatch,
): Promise<PortfolioHolding> {
  const res = await fetch(`/api/portfolio/holdings/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return jsonOrThrow<PortfolioHolding>(res);
}

export async function deleteHolding(id: string): Promise<void> {
  const res = await fetch(`/api/portfolio/holdings/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) {
    throw new Error(`deleteHolding failed: ${res.status}`);
  }
}

export async function fetchAnalytics(): Promise<AnalyticsResponse> {
  const res = await fetch("/api/portfolio/analytics", { credentials: "include" });
  return jsonOrThrow<AnalyticsResponse>(res);
}

export async function refreshPrices(): Promise<RefreshPricesResponse> {
  const res = await fetch("/api/portfolio/refresh-prices", {
    method: "POST",
    credentials: "include",
  });
  if (res.status === 429) {
    const body = await res.json().catch(() => ({ detail: { retry_after: 30 } }));
    const retryAfter = (body?.detail?.retry_after as number | undefined) ?? 30;
    const err = new Error(`Try again in ${retryAfter} seconds`) as Error & {
      retryAfter?: number;
      status?: number;
    };
    err.retryAfter = retryAfter;
    err.status = 429;
    throw err;
  }
  return jsonOrThrow<RefreshPricesResponse>(res);
}

export async function importCsv(text: string): Promise<CsvImportResponse> {
  const res = await fetch("/api/portfolio/import-csv", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  return jsonOrThrow<CsvImportResponse>(res);
}

export function exportCsvUrl(): string {
  return "/api/portfolio/export-csv";
}

// ---------- Time series (Phase 3 + 4) --------------------------------------

export interface ValueSeriesPoint {
  date: string;
  value: string;
}

export interface ValueSeriesResponse {
  timeframe: string;
  actual_span: { start: string; end: string } | null;
  points: ValueSeriesPoint[];
  period_return_abs: string | null;
  period_return_pct: string | null;
}

export interface TickerSeriesPoint {
  ts: string;
  close: string;
}

export interface TickerSeriesResponse {
  timeframe: string;
  series: Record<string, TickerSeriesPoint[]>;
  period_change_pct: Record<string, string | null>;
}

export async function fetchValueSeries(timeframe: string): Promise<ValueSeriesResponse> {
  const res = await fetch(
    `/api/portfolio/value-series?timeframe=${encodeURIComponent(timeframe)}`,
    { credentials: "include" },
  );
  return jsonOrThrow<ValueSeriesResponse>(res);
}

export async function fetchTickerSeries(timeframe: string): Promise<TickerSeriesResponse> {
  const res = await fetch(
    `/api/portfolio/ticker-series?timeframe=${encodeURIComponent(timeframe)}`,
    { credentials: "include" },
  );
  return jsonOrThrow<TickerSeriesResponse>(res);
}

// ---------- Preferences (Phase 2) ------------------------------------------

export type RefreshCadence = "hourly" | "daily" | "weekly" | "manual";

export interface PortfolioPrefs {
  refresh_cadence: RefreshCadence;
  display_currency?: string;
}

export async function fetchPortfolioPrefs(): Promise<PortfolioPrefs> {
  const res = await fetch("/api/portfolio/prefs", { credentials: "include" });
  return jsonOrThrow<PortfolioPrefs>(res);
}

export async function updatePortfolioPrefs(
  patch: Partial<PortfolioPrefs>,
): Promise<PortfolioPrefs> {
  const res = await fetch("/api/portfolio/prefs", {
    method: "PUT",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  return jsonOrThrow<PortfolioPrefs>(res);
}

export async function searchTickers(q: string): Promise<SearchResult[]> {
  if (!q.trim()) return [];
  const res = await fetch(`/api/portfolio/search?q=${encodeURIComponent(q)}`, {
    credentials: "include",
  });
  const body = await jsonOrThrow<{ results: SearchResult[] }>(res);
  return body.results;
}

// ---------- Groups ---------------------------------------------------------

export async function fetchGroups(): Promise<string[]> {
  const res = await fetch("/api/portfolio/groups", { credentials: "include" });
  const body = await jsonOrThrow<{ groups: string[] }>(res);
  return body.groups;
}

export async function createGroup(name: string): Promise<string[]> {
  const res = await fetch("/api/portfolio/groups", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  const body = await jsonOrThrow<{ groups: string[] }>(res);
  return body.groups;
}

export async function renameGroup(name: string, new_name: string): Promise<string[]> {
  const res = await fetch(`/api/portfolio/groups/${encodeURIComponent(name)}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_name }),
  });
  const body = await jsonOrThrow<{ groups: string[] }>(res);
  return body.groups;
}

export async function reorderGroups(order: string[]): Promise<string[]> {
  const res = await fetch("/api/portfolio/groups/reorder", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ order }),
  });
  const body = await jsonOrThrow<{ groups: string[] }>(res);
  return body.groups;
}

export async function deleteGroup(name: string): Promise<string[]> {
  const res = await fetch(`/api/portfolio/groups/${encodeURIComponent(name)}`, {
    method: "DELETE",
    credentials: "include",
  });
  const body = await jsonOrThrow<{ groups: string[] }>(res);
  return body.groups;
}
