import { useCallback, useEffect, useState } from "react";

import {
  createSchedule,
  deleteSchedule,
  fetchSchedules,
  updateSchedule,
  type EuSchedule,
  type EuScheduleCreate,
  type EuScheduleUpdate,
} from "../api/earnings-update";

export function useEuSchedules() {
  const [schedules, setSchedules] = useState<EuSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetchSchedules();
      setSchedules(r.schedules);
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

  const create = useCallback(async (payload: EuScheduleCreate) => {
    const s = await createSchedule(payload);
    setSchedules((prev) =>
      [...prev, s].sort((a, b) => a.time.localeCompare(b.time)),
    );
    return s;
  }, []);

  const update = useCallback(
    async (id: string, payload: EuScheduleUpdate) => {
      const s = await updateSchedule(id, payload);
      setSchedules((prev) => prev.map((x) => (x.id === id ? s : x)));
      return s;
    },
    [],
  );

  const remove = useCallback(async (id: string) => {
    await deleteSchedule(id);
    setSchedules((prev) => prev.filter((x) => x.id !== id));
  }, []);

  return { schedules, loading, error, refresh, create, update, remove };
}
