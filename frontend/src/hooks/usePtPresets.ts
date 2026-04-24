import { useCallback, useEffect, useState } from "react";
import {
  applyPreset,
  createPreset,
  deletePreset,
  listPresets,
  updatePreset,
  type PtPreset,
  type UserConfig,
} from "../api/panic-thermometer";

export interface UsePtPresetsState {
  presets: PtPreset[];
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  create: (name: string, description: string | null) => Promise<PtPreset>;
  rename: (
    id: string,
    payload: { name: string; description: string | null },
  ) => Promise<PtPreset>;
  remove: (id: string) => Promise<void>;
  apply: (id: string) => Promise<UserConfig>;
}

export function usePtPresets(): UsePtPresetsState {
  const [presets, setPresets] = useState<PtPreset[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const rows = await listPresets();
      setPresets(rows);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const create = useCallback(
    async (name: string, description: string | null) => {
      const row = await createPreset(name, description);
      await refresh();
      return row;
    },
    [refresh],
  );

  const rename = useCallback(
    async (id: string, payload: { name: string; description: string | null }) => {
      const row = await updatePreset(id, payload);
      await refresh();
      return row;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await deletePreset(id);
      await refresh();
    },
    [refresh],
  );

  const apply = useCallback(async (id: string) => {
    return applyPreset(id);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { presets, isLoading, error, refresh, create, rename, remove, apply };
}
