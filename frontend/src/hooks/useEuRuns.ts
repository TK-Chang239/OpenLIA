import { useCallback, useEffect, useState } from "react";
import { fetchRuns, type RunSummary, type RunStatus } from "../api/earnings-update";

export interface EuRunsState {
  runs: RunSummary[];
  loading: boolean;
  error: Error | null;
  disabled: boolean;
  refresh: () => Promise<void>;
}

export function useEuRuns(status?: RunStatus): EuRunsState {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [disabled, setDisabled] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await fetchRuns(status);
      setRuns(next);
      setError(null);
    } catch (e) {
      const err = e as Error;
      if (/\b503\b/.test(err.message)) setDisabled(true);
      else setError(err);
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => { void refresh(); }, [refresh]);

  return { runs, loading, error, disabled, refresh };
}
