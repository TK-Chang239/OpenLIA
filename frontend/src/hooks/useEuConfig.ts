import { useCallback, useEffect, useState } from "react";

import {
  fetchConfig,
  updateConfig,
  type EuConfig,
} from "../api/earnings-update";

export function useEuConfig() {
  const [config, setConfig] = useState<EuConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchConfig()
      .then((cfg) => {
        if (!cancelled) {
          setConfig(cfg);
          setLoading(false);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) {
          setError(e);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(async (next: EuConfig) => {
    const saved = await updateConfig(next);
    setConfig(saved);
    return saved;
  }, []);

  return { config, loading, error, save };
}
