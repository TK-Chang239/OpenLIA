import { useCallback, useEffect, useState } from "react";
import {
  listMbRuns,
  type MbRunSummary,
  type MbRunStatus,
} from "../api/morning-briefing";

export interface MbRunsState {
  runs: MbRunSummary[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function useMbRuns(status?: MbRunStatus): MbRunsState {
  const [runs, setRuns] = useState<MbRunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await listMbRuns(status);
      setRuns(next);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { runs, loading, error, refresh };
}
