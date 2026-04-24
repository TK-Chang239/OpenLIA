import { useCallback, useEffect, useState } from "react";

import {
  fetchConfig,
  type MbConfig,
  updateConfig,
} from "../api/morning-briefing";

export function useMbConfig() {
  const [config, setConfig] = useState<MbConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchConfig()
      .then((c) => {
        if (!cancelled) setConfig(c);
      })
      .catch((e) => {
        if (!cancelled) setError(e as Error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(async (next: MbConfig) => {
    const updated = await updateConfig(next);
    setConfig(updated);
    return updated;
  }, []);

  return { config, loading, error, save };
}
