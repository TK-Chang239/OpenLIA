import { useCallback, useEffect, useState } from "react";

import { getHistory, type RsSnapshot } from "../api/retail-sentiment";

export function useRsHistory(ticker: string | null, days = 7) {
  const [history, setHistory] = useState<RsSnapshot[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    if (!ticker) {
      setHistory([]);
      return;
    }
    setLoading(true);
    try {
      const r = await getHistory(ticker, days);
      setHistory(r.snapshots);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [ticker, days]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { history, loading, error, refresh };
}
