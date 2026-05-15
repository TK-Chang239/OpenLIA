import { useCallback, useEffect, useState } from "react";

import {
  ER_CONFIG_DEFAULTS,
  type ErConfig,
  type ErConfigPatch,
  fetchErConfig,
  updateErConfig,
} from "../api/equity-research";

const CACHE_KEY = "openlia.er_config.v1";

function readCachedConfig(): ErConfig | null {
  try {
    const raw =
      typeof window !== "undefined" && window.localStorage
        ? window.localStorage.getItem(CACHE_KEY)
        : null;
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<ErConfig> | null;
    if (!parsed || typeof parsed !== "object") return null;
    return { ...ER_CONFIG_DEFAULTS, ...parsed } as ErConfig;
  } catch {
    return null;
  }
}

function writeCachedConfig(cfg: ErConfig): void {
  try {
    if (typeof window !== "undefined" && window.localStorage) {
      window.localStorage.setItem(CACHE_KEY, JSON.stringify(cfg));
    }
  } catch {
    // ignore quota/serialization failures — cache is best-effort
  }
}

export function useErConfig() {
  const [config, setConfig] = useState<ErConfig>(
    () => readCachedConfig() ?? ER_CONFIG_DEFAULTS,
  );
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchErConfig()
      .then((cfg) => {
        if (cancelled) return;
        setConfig(cfg);
        setLoading(false);
        writeCachedConfig(cfg);
      })
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e);
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const patch = useCallback(async (p: ErConfigPatch) => {
    const next = await updateErConfig(p);
    setConfig(next);
    writeCachedConfig(next);
    return next;
  }, []);

  return { config, loading, error, patch };
}
