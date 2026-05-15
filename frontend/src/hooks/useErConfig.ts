import { useCallback, useEffect, useState } from "react";

import {
  type ErConfig,
  type ErConfigPatch,
  fetchErConfig,
  updateErConfig,
} from "../api/equity-research";

export function useErConfig() {
  const [config, setConfig] = useState<ErConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchErConfig()
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

  const patch = useCallback(async (p: ErConfigPatch) => {
    const next = await updateErConfig(p);
    setConfig(next);
    return next;
  }, []);

  return { config, loading, error, patch };
}
