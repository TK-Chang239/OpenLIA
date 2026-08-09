import { fetchJson } from "./client";

export interface IndexQuote {
  symbol: string;
  label: string;
  value: number;
  previous_close: number | null;
  change_abs: number | null;
  change_pct: number | null;
}

export interface IndicesResponse {
  /** False when no EODHD key/connector is configured. */
  available: boolean;
  indices: IndexQuote[];
}

export const fetchMarketIndices = () =>
  fetchJson<IndicesResponse>("/api/markets/indices");
