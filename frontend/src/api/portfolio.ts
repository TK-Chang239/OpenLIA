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

export async function searchTickers(q: string): Promise<SearchResult[]> {
  const res = await fetch(`/api/portfolio/search?q=${encodeURIComponent(q)}`, {
    credentials: "include",
  });
  const body = await jsonOrThrow<{ results: SearchResult[] }>(res);
  return body.results;
}
