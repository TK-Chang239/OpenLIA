import { useCallback, useEffect, useState } from "react";

import { fetchReports, type RecentReport } from "../api/morning-briefing";

export function useMbReports() {
  const [reports, setReports] = useState<RecentReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { reports: list } = await fetchReports();
      setReports(list);
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

  return { reports, loading, error, refresh };
}
