import { useCallback, useEffect, useState } from "react";

import { getQuotes, type RsQuoteBar } from "../api/retail-sentiment";

export function useRsQuotes(ticker: string | null, days = 30) {
  const [bars, setBars] = useState<RsQuoteBar[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    if (!ticker) {
      setBars([]);
      return;
    }
    setLoading(true);
    try {
      const r = await getQuotes(ticker, days);
      setBars(r.bars ?? []);
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

  return { bars, loading, error, refresh };
}
