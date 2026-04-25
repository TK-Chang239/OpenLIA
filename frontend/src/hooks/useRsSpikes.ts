import { useCallback, useEffect, useState } from "react";

import { getSpikes, type RsSpike } from "../api/retail-sentiment";

export function useRsSpikes() {
  const [spikes, setSpikes] = useState<RsSpike[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await getSpikes();
      setSpikes(r.spikes);
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

  return { spikes, loading, error, refresh };
}
