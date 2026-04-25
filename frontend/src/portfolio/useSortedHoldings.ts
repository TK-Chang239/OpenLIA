import { useMemo } from "react";

import type { PortfolioHolding, PositionAnalytic } from "../api/portfolio";
import { useLocalPref } from "./useLocalPref";

export type SortKey = "alpha-asc" | "alpha-desc" | "price-desc" | "price-asc";

const ALL_KEYS: readonly SortKey[] = [
  "alpha-asc",
  "alpha-desc",
  "price-desc",
  "price-asc",
];

const isSortKey = (v: string): v is SortKey =>
  (ALL_KEYS as readonly string[]).includes(v);

export const SORT_LABELS: Record<SortKey, string> = {
  "alpha-asc": "A → Z",
  "alpha-desc": "Z → A",
  "price-desc": "Price ↓",
  "price-asc": "Price ↑",
};

/**
 * useSortedHoldings — returns holdings sorted by the user's per-group
 * preference (persisted to `portfolio:sort:{groupId}` in localStorage).
 */
export function useSortedHoldings(
  holdings: readonly PortfolioHolding[],
  pricesByHolding: ReadonlyMap<string, PositionAnalytic | undefined>,
  groupId: string,
): {
  readonly sorted: PortfolioHolding[];
  readonly sortKey: SortKey;
  readonly setSortKey: (k: SortKey) => void;
} {
  const [stored, setStored] = useLocalPref<string>(
    `portfolio:sort:${groupId}`,
    "alpha-asc",
  );
  const sortKey: SortKey = isSortKey(stored) ? stored : "alpha-asc";

  const sorted = useMemo(() => {
    const list = [...holdings];
    const priceFor = (h: PortfolioHolding): number => {
      const raw = pricesByHolding.get(h.id)?.last_price;
      const n = raw === null || raw === undefined ? NaN : Number(raw);
      return Number.isFinite(n) ? n : -Infinity;
    };
    switch (sortKey) {
      case "alpha-asc":
        return list.sort((a, b) => a.ticker.localeCompare(b.ticker));
      case "alpha-desc":
        return list.sort((a, b) => b.ticker.localeCompare(a.ticker));
      case "price-desc":
        return list.sort((a, b) => priceFor(b) - priceFor(a));
      case "price-asc":
        return list.sort((a, b) => priceFor(a) - priceFor(b));
      default:
        return list;
    }
  }, [holdings, pricesByHolding, sortKey]);

  return {
    sorted,
    sortKey,
    setSortKey: (k: SortKey) => setStored(k),
  } as const;
}
