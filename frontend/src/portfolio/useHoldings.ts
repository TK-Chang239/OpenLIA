import { useCallback, useEffect, useState } from "react";

import {
  createHolding,
  deleteHolding,
  fetchHoldings,
  type HoldingInput,
  type PortfolioHolding,
} from "../api/portfolio";

export interface UseHoldingsResult {
  readonly holdings: PortfolioHolding[];
  readonly loading: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
  readonly add: (input: HoldingInput) => Promise<PortfolioHolding>;
  readonly remove: (id: string) => Promise<PortfolioHolding | undefined>;
}

/** useHoldings — list, add, remove with optimistic snapshot for Undo. */
export function useHoldings(): UseHoldingsResult {
  const [holdings, setHoldings] = useState<PortfolioHolding[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setHoldings(await fetchHoldings());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const add = useCallback(
    async (input: HoldingInput) => {
      const created = await createHolding(input);
      setHoldings((prev) => [...prev, created]);
      return created;
    },
    [],
  );

  const remove = useCallback(
    async (id: string) => {
      const snapshot = holdings.find((h) => h.id === id);
      await deleteHolding(id);
      setHoldings((prev) => prev.filter((h) => h.id !== id));
      return snapshot;
    },
    [holdings],
  );

  return { holdings, loading, error, reload, add, remove } as const;
}
