// Portfolio domain fixtures for demo mode. Registers every /api/portfolio/*
// route the Portfolio page and the Home portfolio-glance card touch, backed by
// the shared persona book. Two markets: "us" (USD book) and "tw" (TWD book).
// Read-only: mutating endpoints echo a plausible object; nothing persists.

import { register, json } from "../registry";
import type { DemoRequest } from "../registry";
import { DEMO_NOW_ISO, daysAgo } from "../clock";
import {
  US_HOLDINGS,
  TW_HOLDINGS,
  type Holding,
} from "./persona";
import type {
  AnalyticsResponse,
  PortfolioHolding,
  PositionAnalytic,
  ValueSeriesResponse,
  ValueSeriesPoint,
  TickerSeriesResponse,
  TickerSeriesPoint,
} from "../../api/portfolio";

// --- Markets ---------------------------------------------------------------

type Market = "us" | "tw";

const MARKET_CURRENCY: Record<Market, string> = { us: "USD", tw: "TWD" };

/** Normalize the ?market= query into a known market id, defaulting to US. */
function marketOf(req: DemoRequest): Market {
  const raw = (req.url.searchParams.get("market") ?? "").toLowerCase();
  if (raw === "tw" || raw === "taiwan") return "tw";
  return "us";
}

function bookFor(market: Market): Holding[] {
  return market === "tw" ? TW_HOLDINGS : US_HOLDINGS;
}

/** A stable holding id per persona symbol, e.g. "us-nvda" / "tw-2330-tw". */
function holdingId(market: Market, symbol: string): string {
  return `${market}-${symbol.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
}

/** One sector-based group per holding so the allocation card populates. */
function groupFor(h: Holding): string {
  return h.sector;
}

// --- Derived per-position numbers ------------------------------------------

interface Derived {
  h: Holding;
  id: string;
  costBasisTotal: number; // shares * avgCost
  marketValue: number; // shares * last
  unrealizedPl: number; // marketValue - costBasisTotal
  unrealizedPlPct: number; // fraction: unrealizedPl / costBasisTotal
  previousClose: number; // last / (1 + dayChangePct/100)
  dayChangeAbsPerShare: number; // last - previousClose
  dayChangeAbsTotal: number; // dayChangeAbsPerShare * shares
  dayChangePctFrac: number; // fraction: dayChangePct / 100
}

function derive(market: Market, h: Holding): Derived {
  const costBasisTotal = h.shares * h.avgCost;
  const marketValue = h.shares * h.last;
  const unrealizedPl = marketValue - costBasisTotal;
  const unrealizedPlPct = costBasisTotal !== 0 ? unrealizedPl / costBasisTotal : 0;
  const previousClose = h.last / (1 + h.dayChangePct / 100);
  const dayChangeAbsPerShare = h.last - previousClose;
  const dayChangeAbsTotal = dayChangeAbsPerShare * h.shares;
  return {
    h,
    id: holdingId(market, h.symbol),
    costBasisTotal,
    marketValue,
    unrealizedPl,
    unrealizedPlPct,
    previousClose,
    dayChangeAbsPerShare,
    dayChangeAbsTotal,
    dayChangePctFrac: h.dayChangePct / 100,
  };
}

function num(n: number, dp = 2): string {
  return n.toFixed(dp);
}

// --- Holdings list ---------------------------------------------------------

function holdingRow(market: Market, h: Holding): PortfolioHolding {
  return {
    id: holdingId(market, h.symbol),
    ticker: h.symbol,
    name: h.name,
    shares: num(h.shares, 4),
    cost_basis: num(h.avgCost, 4),
    currency: h.currency,
    groups: [groupFor(h)],
    notes_text: null,
    added_at: daysAgo(180),
    updated_at: DEMO_NOW_ISO,
  };
}

function holdingsFor(market: Market): PortfolioHolding[] {
  return bookFor(market).map((h) => holdingRow(market, h));
}

// --- Analytics -------------------------------------------------------------

function analyticsFor(market: Market): AnalyticsResponse {
  const book = bookFor(market);
  const derived = book.map((h) => derive(market, h));

  const totalMv = derived.reduce((s, d) => s + d.marketValue, 0);
  const totalCost = derived.reduce((s, d) => s + d.costBasisTotal, 0);
  const totalPl = totalMv - totalCost;
  const totalPlPct = totalCost !== 0 ? totalPl / totalCost : 0;

  const positions: PositionAnalytic[] = derived.map((d) => ({
    holding_id: d.id,
    ticker: d.h.symbol,
    shares: num(d.h.shares, 4),
    cost_basis: num(d.h.avgCost, 4),
    last_price: num(d.h.last, 4),
    market_value: num(d.marketValue),
    unrealized_pl: num(d.unrealizedPl),
    unrealized_pl_pct: num(d.unrealizedPlPct, 6), // fraction
    weight: num(totalMv !== 0 ? d.marketValue / totalMv : 0, 6), // fraction
    currency: d.h.currency,
    previous_close: num(d.previousClose, 4),
    day_change_abs: num(d.dayChangeAbsTotal),
    day_change_pct: num(d.dayChangePctFrac, 6), // fraction
  }));

  // Group-weighted allocations (share of total NAV per group), as fractions.
  const allocations: Record<string, string> = {};
  for (const d of derived) {
    const g = groupFor(d.h);
    const prev = allocations[g] ? Number(allocations[g]) : 0;
    allocations[g] = num(prev + (totalMv !== 0 ? d.marketValue / totalMv : 0), 6);
  }

  const currency = MARKET_CURRENCY[market];
  return {
    total_market_value: num(totalMv),
    total_cost_basis: num(totalCost),
    total_unrealized_pl: num(totalPl),
    total_unrealized_pl_pct: num(totalPlPct, 6),
    positions,
    allocations,
    last_quote_at: DEMO_NOW_ISO,
    display_currency: currency,
    currencies_present: [currency],
    needs_fx: false,
    fx_unavailable: false,
  };
}

// --- Value series ----------------------------------------------------------

// Timeframe -> (number of points, days spanned). Covers both the Home card
// tabs (1d/1m/3m/1y/all) and the Portfolio page ranges (1w/6m/ytd/5y).
const TIMEFRAME_SHAPE: Record<string, { points: number; days: number }> = {
  "1d": { points: 32, days: 1 },
  "1w": { points: 35, days: 7 },
  "1m": { points: 30, days: 30 },
  "3m": { points: 45, days: 90 },
  "6m": { points: 60, days: 180 },
  ytd: { points: 66, days: 219 }, // ~Jan 1 -> demo now (2026-08-07)
  "1y": { points: 80, days: 365 },
  "5y": { points: 120, days: 365 * 5 },
  all: { points: 120, days: 365 * 3 },
};

function totalMarketValue(market: Market): number {
  return bookFor(market).reduce((s, h) => s + h.shares * h.last, 0);
}

/** A smooth upward-trending NAV path ending at the current market value.
 *  Deterministic (seeded wobble) so the demo looks identical every load. */
function valueSeriesFor(market: Market, timeframe: string): ValueSeriesResponse {
  const shape = TIMEFRAME_SHAPE[timeframe] ?? TIMEFRAME_SHAPE["1m"];
  const end = totalMarketValue(market);
  // Longer windows started lower (more cumulative growth into today).
  const growth =
    shape.days <= 1 ? 0.012 : Math.min(0.9, 0.06 + shape.days / 480);
  const start = end / (1 + growth);

  const n = shape.points;
  const points: ValueSeriesPoint[] = [];
  for (let i = 0; i < n; i++) {
    const t = n === 1 ? 1 : i / (n - 1);
    const base = start + (end - start) * t;
    // Deterministic bounded wobble, damped to zero at the last point so the
    // series lands exactly on today's NAV.
    const wobble =
      Math.sin(i * 1.7 + (market === "tw" ? 2.1 : 0.5)) *
      (end - start) *
      0.06 *
      (1 - t);
    const value = base + wobble;
    const daysBack = Math.round(shape.days * (1 - t));
    const ts = daysAgo(daysBack);
    const date = ts.slice(0, 10);
    points.push({ date, value: num(value), ts });
  }

  const first = Number(points[0].value);
  const last = Number(points[points.length - 1].value);
  const periodAbs = last - first;
  const periodPct = first !== 0 ? periodAbs / first : 0; // fraction

  return {
    timeframe,
    actual_span: { start: points[0].date, end: points[points.length - 1].date },
    points,
    period_return_abs: num(periodAbs),
    period_return_pct: num(periodPct, 6),
  };
}

// --- Ticker series (row sparklines) ----------------------------------------

/** Per-ticker daily closes over the window, keyed by UPPERCASE ticker (the
 *  HoldingsTable looks them up via ticker.toUpperCase()). */
function tickerSeriesFor(market: Market, timeframe: string): TickerSeriesResponse {
  const shape = TIMEFRAME_SHAPE[timeframe] ?? TIMEFRAME_SHAPE["1w"];
  const book = bookFor(market);
  const series: Record<string, TickerSeriesPoint[]> = {};
  const periodChange: Record<string, string | null> = {};

  for (const h of book) {
    const end = h.last;
    const start = h.last / (1 + h.dayChangePct / 100 + 0.03); // mild net drift
    const n = Math.min(shape.points, 40);
    const pts: TickerSeriesPoint[] = [];
    for (let i = 0; i < n; i++) {
      const t = n === 1 ? 1 : i / (n - 1);
      const base = start + (end - start) * t;
      const wobble =
        Math.sin(i * 2.3 + h.symbol.length) * (end * 0.01) * (1 - t);
      const close = base + wobble;
      const daysBack = Math.round(shape.days * (1 - t));
      pts.push({ ts: daysAgo(daysBack), close: num(close, 4) });
    }
    const key = h.symbol.toUpperCase();
    series[key] = pts;
    const f = Number(pts[0].close);
    periodChange[key] = f !== 0 ? num((Number(pts[pts.length - 1].close) - f) / f, 6) : null;
  }

  return { timeframe, series, period_change_pct: periodChange };
}

// --- Groups ----------------------------------------------------------------

// Union of the sector groups across both books, deduped and stable-ordered.
const ALL_GROUPS: string[] = (() => {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const h of [...US_HOLDINGS, ...TW_HOLDINGS]) {
    const g = groupFor(h);
    if (!seen.has(g)) {
      seen.add(g);
      out.push(g);
    }
  }
  return out;
})();

// --- Routes ----------------------------------------------------------------

register([
  // Holdings list for the active market.
  {
    method: "GET",
    pattern: "/api/portfolio/holdings",
    handler: (req) => json(holdingsFor(marketOf(req))),
  },
  // Create holding (read-only: echo a plausible new row).
  {
    method: "POST",
    pattern: "/api/portfolio/holdings",
    handler: (req) => {
      const market = marketOf(req);
      const body = (req.body ?? {}) as {
        ticker?: string;
        shares?: string | null;
        cost_basis?: string | null;
        currency?: string;
        notes?: string | null;
        groups?: string[];
      };
      const ticker = (body.ticker ?? "DEMO").toUpperCase();
      const row: PortfolioHolding = {
        id: `${market}-new-${ticker.toLowerCase()}`,
        ticker,
        name: null,
        shares: body.shares ?? null,
        cost_basis: body.cost_basis ?? null,
        currency: body.currency ?? MARKET_CURRENCY[market],
        groups: body.groups ?? [],
        notes_text: body.notes ?? null,
        added_at: DEMO_NOW_ISO,
        updated_at: DEMO_NOW_ISO,
      };
      return json(row, 201);
    },
  },
  // Update holding (read-only: echo the patched row).
  {
    method: "PATCH",
    pattern: "/api/portfolio/holdings/:id",
    handler: (req) => {
      const body = (req.body ?? {}) as Record<string, unknown>;
      const row: PortfolioHolding = {
        id: req.params.id,
        ticker: "DEMO",
        name: null,
        shares: (body.shares as string | null) ?? null,
        cost_basis: (body.cost_basis as string | null) ?? null,
        currency: (body.currency as string) ?? "USD",
        groups: (body.groups as string[]) ?? [],
        notes_text: (body.notes as string | null) ?? null,
        added_at: daysAgo(30),
        updated_at: DEMO_NOW_ISO,
      };
      return json(row);
    },
  },
  // Delete holding (read-only: benign 204-style success).
  {
    method: "DELETE",
    pattern: "/api/portfolio/holdings/:id",
    handler: () => json({ ok: true }),
  },

  // Analytics: totals + per-position derived numbers for the active market.
  {
    method: "GET",
    pattern: "/api/portfolio/analytics",
    handler: (req) => json(analyticsFor(marketOf(req))),
  },

  // Refresh prices (read-only: echo current prices, no persistence).
  {
    method: "POST",
    pattern: "/api/portfolio/refresh-prices",
    handler: (req) => {
      const market = marketOf(req);
      const prices: Record<string, string | null> = {};
      for (const h of bookFor(market)) prices[h.symbol] = num(h.last, 4);
      return json({ prices });
    },
  },

  // CSV import / export (read-only benign responses).
  {
    method: "POST",
    pattern: "/api/portfolio/import-csv",
    handler: () => json({ created: [], errors: [] }),
  },
  {
    method: "GET",
    pattern: "/api/portfolio/export-csv",
    handler: () =>
      json(
        "ticker,shares,cost_basis,currency\nNVDA,120,98.40,USD\n",
      ),
  },

  // Portfolio NAV value series per timeframe/market.
  {
    method: "GET",
    pattern: "/api/portfolio/value-series",
    handler: (req) => {
      const tf = (req.url.searchParams.get("timeframe") ?? "1m").toLowerCase();
      return json(valueSeriesFor(marketOf(req), tf));
    },
  },
  // Per-ticker series for row sparklines.
  {
    method: "GET",
    pattern: "/api/portfolio/ticker-series",
    handler: (req) => {
      const tf = (req.url.searchParams.get("timeframe") ?? "1w").toLowerCase();
      return json(tickerSeriesFor(marketOf(req), tf));
    },
  },

  // Preferences (read-only: fixed cadence, echo on write).
  {
    method: "GET",
    pattern: "/api/portfolio/prefs",
    handler: () => json({ refresh_cadence: "daily", display_currency: "USD" }),
  },
  {
    method: "PUT",
    pattern: "/api/portfolio/prefs",
    handler: (req) => {
      const body = (req.body ?? {}) as {
        refresh_cadence?: string;
        display_currency?: string;
      };
      return json({
        refresh_cadence: body.refresh_cadence ?? "daily",
        display_currency: body.display_currency ?? "USD",
      });
    },
  },

  // Ticker search (used by AddEditDrawer typeahead).
  {
    method: "GET",
    pattern: "/api/portfolio/search",
    handler: (req) => {
      const q = (req.url.searchParams.get("q") ?? "").trim().toUpperCase();
      if (!q) return json({ results: [] });
      const pool = [...US_HOLDINGS, ...TW_HOLDINGS];
      const results = pool
        .filter(
          (h) =>
            h.symbol.toUpperCase().includes(q) ||
            h.name.toUpperCase().includes(q),
        )
        .map((h) => ({
          ticker: h.symbol,
          name: h.name,
          exchange: h.currency === "TWD" ? "TWSE" : "NASDAQ",
          already_added: true,
        }));
      return json({ results });
    },
  },

  // Groups (read-only: fixed set derived from persona sectors).
  {
    method: "GET",
    pattern: "/api/portfolio/groups",
    handler: () => json({ groups: ALL_GROUPS }),
  },
  {
    method: "POST",
    pattern: "/api/portfolio/groups",
    handler: (req) => {
      const body = (req.body ?? {}) as { name?: string };
      const name = body.name?.trim();
      const groups = name && !ALL_GROUPS.includes(name) ? [...ALL_GROUPS, name] : ALL_GROUPS;
      return json({ groups });
    },
  },
  {
    method: "PATCH",
    pattern: "/api/portfolio/groups/:name",
    handler: (req) => {
      const body = (req.body ?? {}) as { new_name?: string };
      const next = ALL_GROUPS.map((g) =>
        g === req.params.name ? body.new_name ?? g : g,
      );
      return json({ groups: next });
    },
  },
  {
    method: "POST",
    pattern: "/api/portfolio/groups/reorder",
    handler: (req) => {
      const body = (req.body ?? {}) as { order?: string[] };
      return json({ groups: body.order ?? ALL_GROUPS });
    },
  },
  {
    method: "DELETE",
    pattern: "/api/portfolio/groups/:name",
    handler: (req) =>
      json({ groups: ALL_GROUPS.filter((g) => g !== req.params.name) }),
  },
]);
