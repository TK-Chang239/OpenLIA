import { useCallback, useEffect, useState } from "react";

import {
  fetchAnalytics,
  refreshPrices,
  type AnalyticsResponse,
} from "../api/portfolio";

export interface UseAnalyticsResult {
  readonly analytics: AnalyticsResponse | null;
  readonly loading: boolean;
  readonly error: string | null;
  readonly reload: () => Promise<void>;
  readonly refresh: () => Promise<void>;
}

/** useAnalytics — analytics + refresh with rate-limit error surfacing. */
export function useAnalytics(market?: string): UseAnalyticsResult {
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAnalytics(await fetchAnalytics(market));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [market]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const refresh = useCallback(async () => {
    setError(null);
    await refreshPrices(market);
    await reload();
  }, [reload, market]);

  return { analytics, loading, error, reload, refresh } as const;
}
