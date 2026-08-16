import type {
  AnalyticsResponse,
  PortfolioHolding,
} from "../api/portfolio";

export const UNTAGGED = "Untagged" as const;

export interface AllocationRow {
  group: string; // "Untagged" for holdings with no group
  marketValue: number;
  pct: number; // 0..100
  count: number;
}

/** Compute group-allocation rows from holdings + analytics positions.
 *
 *  Single-group constraint: each holding has groups.length <= 1.
 *  Holdings with groups.length === 0 collect under UNTAGGED.
 *  Holdings with no analytics position (e.g. missing price) contribute 0.
 *  Returns rows sorted by pct desc; Untagged is always last when present. */
export function computeAllocation(
  holdings: readonly PortfolioHolding[],
  analytics: AnalyticsResponse | null,
): AllocationRow[] {
  if (!analytics) return [];
  // Group allocation is only meaningful within a single currency: summing raw market
  // values across currencies (or dividing by a cross-currency total) is not valid
  // without FX conversion, which is intentionally not performed.
  if ((analytics.currencies_present?.length ?? 0) > 1) return [];

  const totalMv = Number(analytics.total_market_value);
  if (!Number.isFinite(totalMv) || totalMv <= 0) return [];

  const mvByHoldingId = new Map<string, number>();
  for (const p of analytics.positions) {
    const v = p.market_value === null ? 0 : Number(p.market_value);
    mvByHoldingId.set(p.holding_id, Number.isFinite(v) ? v : 0);
  }

  const buckets = new Map<string, { mv: number; count: number }>();
  for (const h of holdings) {
    const group = h.groups[0] ?? UNTAGGED;
    const mv = mvByHoldingId.get(h.id) ?? 0;
    const cur = buckets.get(group) ?? { mv: 0, count: 0 };
    cur.mv += mv;
    cur.count += 1;
    buckets.set(group, cur);
  }

  const rows: AllocationRow[] = [];
  for (const [group, { mv, count }] of buckets.entries()) {
    rows.push({
      group,
      marketValue: mv,
      pct: (mv / totalMv) * 100,
      count,
    });
  }

  rows.sort((a, b) => {
    if (a.group === UNTAGGED && b.group !== UNTAGGED) return 1;
    if (b.group === UNTAGGED && a.group !== UNTAGGED) return -1;
    return b.pct - a.pct;
  });
  return rows;
}
