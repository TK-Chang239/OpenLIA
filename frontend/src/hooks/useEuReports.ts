import { useCallback, useEffect, useState } from "react";

import {
  fetchRecentReports,
  type RecentReport,
} from "../api/earnings-update";

export function useEuReports(limit = 5) {
  const [reports, setReports] = useState<RecentReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchRecentReports(limit);
      setReports(r.reports);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { reports, loading, error, refresh };
}
