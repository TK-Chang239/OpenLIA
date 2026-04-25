import { useCallback, useEffect, useState } from "react";

import {
  getConfig,
  updateConfig,
  type RsConfig,
  type RsConfigUpdate,
} from "../api/retail-sentiment";

export function useRsConfig() {
  const [config, setConfig] = useState<RsConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    getConfig()
      .then((r) => {
        if (!cancelled) setConfig(r);
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

  const save = useCallback(
    async (payload: RsConfigUpdate) => {
      // Optimistic merge so the UI feels responsive.
      const previous = config;
      if (config) {
        setConfig({
          ...config,
          ...(payload.active_tab !== undefined
            ? { active_tab: payload.active_tab }
            : {}),
          ...(payload.refresh_interval_minutes !== undefined
            ? { refresh_interval_minutes: payload.refresh_interval_minutes }
            : {}),
          ...(payload.metric_settings !== undefined
            ? { metric_settings: payload.metric_settings }
            : {}),
          ...(payload.filter_presets !== undefined
            ? { filter_presets: payload.filter_presets }
            : {}),
        });
      }
      try {
        const updated = await updateConfig(payload);
        setConfig(updated);
        return updated;
      } catch (e) {
        // Roll back on failure.
        if (previous) setConfig(previous);
        setError(e as Error);
        throw e;
      }
    },
    [config],
  );

  return { config, loading, error, save };
}
