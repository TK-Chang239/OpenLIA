import { useCallback, useEffect, useState } from "react";

import {
  addWatchlistEntry,
  fetchWatchlist,
  removeWatchlistEntry,
  type WatchlistEntry,
} from "../api/earnings-update";
import { getDemoWatchlist, isDemoMode } from "../lib/earnings-update/demo-data";

export function useEuWatchlist() {
  const [entries, setEntries] = useState<WatchlistEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    if (isDemoMode()) {
      setEntries(getDemoWatchlist());
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const r = await fetchWatchlist();
      setEntries(r.entries);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const add = useCallback(async (ticker: string) => {
    const entry = await addWatchlistEntry(ticker);
    setEntries((prev) => [entry, ...prev]);
    return entry;
  }, []);

  const remove = useCallback(
    async (entryId: string) => {
      const snapshot = entries;
      setEntries((prev) => prev.filter((e) => e.id !== entryId));
      try {
        await removeWatchlistEntry(entryId);
      } catch (e) {
        setEntries(snapshot);
        throw e;
      }
    },
    [entries],
  );

  return { entries, loading, error, refresh, add, remove };
}
