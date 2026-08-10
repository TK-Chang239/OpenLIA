// Canonical demo dataset. One fictional investor's tech-tilted book, shared
// across every domain module so the same tickers, names, and prices appear in
// Portfolio, watchlists, reports, and dashboards. Illustrative numbers only,
// frozen to the demo "as of" date.

export interface Holding {
  symbol: string;
  name: string;
  sector: string;
  currency: "USD" | "TWD";
  shares: number;
  avgCost: number; // per share, in `currency`
  last: number; // current price, in `currency`
  dayChangePct: number;
}

export const INVESTOR = {
  displayName: "TK Chang",
  firstName: "TK",
} as const;

export const US_HOLDINGS: Holding[] = [
  { symbol: "NVDA", name: "NVIDIA", sector: "Semiconductors", currency: "USD", shares: 120, avgCost: 98.4, last: 176.2, dayChangePct: 1.9 },
  { symbol: "AAPL", name: "Apple", sector: "Consumer Electronics", currency: "USD", shares: 80, avgCost: 171.2, last: 233.5, dayChangePct: 0.4 },
  { symbol: "MSFT", name: "Microsoft", sector: "Software", currency: "USD", shares: 60, avgCost: 372.0, last: 512.9, dayChangePct: 0.8 },
  { symbol: "GOOGL", name: "Alphabet", sector: "Interactive Media", currency: "USD", shares: 90, avgCost: 138.5, last: 201.7, dayChangePct: -0.3 },
  { symbol: "AMZN", name: "Amazon", sector: "Internet Retail", currency: "USD", shares: 70, avgCost: 152.0, last: 224.1, dayChangePct: 1.1 },
  { symbol: "PLTR", name: "Palantir", sector: "Software", currency: "USD", shares: 200, avgCost: 24.6, last: 158.3, dayChangePct: 3.2 },
];

export const TW_HOLDINGS: Holding[] = [
  { symbol: "2330.TW", name: "TSMC", sector: "Semiconductors", currency: "TWD", shares: 2000, avgCost: 720, last: 1085, dayChangePct: 1.2 },
  { symbol: "2317.TW", name: "Hon Hai (Foxconn)", sector: "Electronics Manufacturing", currency: "TWD", shares: 3000, avgCost: 145, last: 208, dayChangePct: 0.6 },
  { symbol: "2454.TW", name: "MediaTek", sector: "Semiconductors", currency: "TWD", shares: 400, avgCost: 980, last: 1360, dayChangePct: -0.4 },
];

export const WATCHLIST_US = ["NVDA", "AMD", "TSM", "AVGO", "META", "AAPL"] as const;

const NAME_BY_SYMBOL: Record<string, string> = {
  ...Object.fromEntries([...US_HOLDINGS, ...TW_HOLDINGS].map((h) => [h.symbol, h.name])),
  AMD: "Advanced Micro Devices",
  TSM: "TSMC (ADR)",
  AVGO: "Broadcom",
  META: "Meta Platforms",
};

export function companyName(symbol: string): string {
  return NAME_BY_SYMBOL[symbol] ?? symbol;
}

export function marketValueUSD(h: Holding): number {
  // TWD -> USD at a frozen illustrative rate for cross-book totals.
  const fx = h.currency === "TWD" ? 1 / 32.5 : 1;
  return h.shares * h.last * fx;
}
