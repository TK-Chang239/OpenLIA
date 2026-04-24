import { useCallback, useEffect, useState } from "react";
import {
  fetchConfig,
  saveConfig,
  type UserConfig,
} from "../api/panic-thermometer";

export interface UsePtConfigState {
  config: UserConfig | null;
  isLoading: boolean;
  error: Error | null;
  save: (next: Pick<UserConfig, "panel_config" | "composite_settings">) => Promise<void>;
  refresh: () => Promise<void>;
}

export function usePtConfig(): UsePtConfigState {
  const [config, setConfig] = useState<UserConfig | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const cfg = await fetchConfig();
      setConfig(cfg);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const save = useCallback(
    async (next: Pick<UserConfig, "panel_config" | "composite_settings">) => {
      const updated = await saveConfig(next);
      setConfig(updated);
    },
    [],
  );

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { config, isLoading, error, save, refresh };
}
