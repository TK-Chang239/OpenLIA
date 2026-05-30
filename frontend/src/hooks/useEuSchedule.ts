import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchSchedule, type EuScheduleEntry } from "../api/earnings-update";

export function useEuSchedule() {
  const [schedule, setSchedule] = useState<EuScheduleEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { schedule: rows } = await fetchSchedule();
      setSchedule(rows);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  // Soonest pending release per ticker, for the watchlist-card join.
  const byTicker = useMemo(() => {
    const m = new Map<string, EuScheduleEntry>();
    for (const row of schedule) {
      if (row.status !== "pending") continue;
      const cur = m.get(row.ticker);
      if (!cur || row.scheduled_run_at < cur.scheduled_run_at) m.set(row.ticker, row);
    }
    return m;
  }, [schedule]);

  return { schedule, byTicker, loading, error, refresh };
}
