import { useCallback, useEffect, useState } from "react";

import {
  listMbInstructions,
  createMbInstructions,
  deleteMbInstructions,
  type MbInstructions,
} from "../api/morning-briefing";

export function useMbInstructions() {
  const [instructions, setInstructions] = useState<MbInstructions[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await listMbInstructions();
      setInstructions(rows);
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

  const upload = useCallback(
    async (name: string, file: File) => {
      const created = await createMbInstructions(name, file);
      await refresh();
      return created;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteMbInstructions(id);
      await refresh();
    },
    [refresh],
  );

  return { instructions, loading, error, refresh, upload, remove };
}
