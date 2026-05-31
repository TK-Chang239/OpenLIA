import { useCallback, useEffect, useState } from "react";

import { getEuDataSources, type DataSource } from "../api/earnings-update";

export function useEuDataSources(providerKind: string, model: string) {
  const [sources, setSources] = useState<DataSource[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const info = await getEuDataSources({ provider_kind: providerKind, model });
      setSources(info.sources);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [providerKind, model]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { sources, loading, error, refresh };
}
