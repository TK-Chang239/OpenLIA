import { useCallback, useEffect, useState } from "react";

import {
  getMbDataSources,
  type MbDataSource,
  type MbDataSourcesParams,
} from "../api/morning-briefing";

export function useMbDataSources(params: MbDataSourcesParams = {}) {
  const [sources, setSources] = useState<MbDataSource[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Stringify params to use as a stable effect dependency.
  const paramsKey = JSON.stringify(params);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const info = await getMbDataSources(params);
      setSources(info.sources);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { sources, loading, error, refresh };
}
