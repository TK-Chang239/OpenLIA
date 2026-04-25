import { useCallback, useEffect, useState } from "react";

import { getDashboard, type RsDashboard } from "../api/retail-sentiment";

export function useRsDashboard(refreshIntervalMinutes: number | null = null) {
  const [dashboard, setDashboard] = useState<RsDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await getDashboard();
      setDashboard(r);
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

  useEffect(() => {
    if (!refreshIntervalMinutes || refreshIntervalMinutes <= 0) return;
    const handle = window.setInterval(
      () => {
        void refresh();
      },
      Math.max(60, refreshIntervalMinutes * 60) * 1000,
    );
    return () => window.clearInterval(handle);
  }, [refresh, refreshIntervalMinutes]);

  return { dashboard, loading, error, refresh };
}
