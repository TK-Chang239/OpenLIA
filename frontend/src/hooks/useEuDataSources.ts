import { useCallback, useEffect, useState } from "react";

import { getEuDataSources, type DataSourcesInfo } from "../api/earnings-update";

export function useEuDataSources(providerKind: string, model: string) {
  const [dataSources, setDataSources] = useState<DataSourcesInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const info = await getEuDataSources({ provider_kind: providerKind, model });
      setDataSources(info);
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

  return { dataSources, loading, error, refresh };
}
