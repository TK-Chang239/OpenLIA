import { useCallback, useEffect, useState } from "react";

import {
  deleteSchedule,
  fetchSchedule,
  type MbSchedule,
  type MbScheduleUpsert,
  upsertSchedule,
} from "../api/morning-briefing";

export function useMbSchedule() {
  const [schedule, setSchedule] = useState<MbSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchSchedule()
      .then((r) => {
        if (!cancelled) setSchedule(r.schedule);
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

  const save = useCallback(async (payload: MbScheduleUpsert) => {
    const updated = await upsertSchedule(payload);
    setSchedule(updated);
    return updated;
  }, []);

  const remove = useCallback(async () => {
    await deleteSchedule();
    setSchedule(null);
  }, []);

  return { schedule, loading, error, save, remove };
}
