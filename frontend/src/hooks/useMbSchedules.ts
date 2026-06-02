import { useCallback, useEffect, useState } from "react";

import {
  listMbSchedules,
  createMbSchedule,
  updateMbSchedule,
  deleteMbSchedule,
  type MbSchedule,
  type MbScheduleIn,
} from "../api/morning-briefing";

export function useMbSchedules() {
  const [schedules, setSchedules] = useState<MbSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await listMbSchedules();
      setSchedules(Array.isArray(list) ? list : []);
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

  const create = useCallback(
    async (payload: MbScheduleIn) => {
      const created = await createMbSchedule(payload);
      await refresh();
      return created;
    },
    [refresh],
  );

  const update = useCallback(
    async (id: string, payload: MbScheduleIn) => {
      const updated = await updateMbSchedule(id, payload);
      await refresh();
      return updated;
    },
    [refresh],
  );

  const remove = useCallback(
    async (id: string) => {
      await deleteMbSchedule(id);
      await refresh();
    },
    [refresh],
  );

  return { schedules, loading, error, create, update, remove, refresh };
}
