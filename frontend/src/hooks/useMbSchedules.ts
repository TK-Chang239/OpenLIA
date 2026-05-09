import { useCallback, useEffect, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  fetchSchedules,
  type MbSchedule,
  type MbScheduleUpsert,
  updateSchedule,
} from "../api/morning-briefing";

export function useMbSchedules() {
  const [schedules, setSchedules] = useState<MbSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    const list = await fetchSchedules();
    setSchedules(Array.isArray(list) ? list : []);
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetchSchedules()
      .then((list) => {
        if (!cancelled) setSchedules(Array.isArray(list) ? list : []);
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

  const create = useCallback(async (payload: MbScheduleUpsert) => {
    const created = await createSchedule(payload);
    setSchedules((prev) => [...prev, created]);
    return created;
  }, []);

  const update = useCallback(
    async (id: string, payload: MbScheduleUpsert) => {
      const updated = await updateSchedule(id, payload);
      setSchedules((prev) => prev.map((s) => (s.id === id ? updated : s)));
      return updated;
    },
    [],
  );

  const remove = useCallback(async (id: string) => {
    await deleteSchedule(id);
    setSchedules((prev) => prev.filter((s) => s.id !== id));
  }, []);

  return { schedules, loading, error, create, update, remove, refresh };
}
