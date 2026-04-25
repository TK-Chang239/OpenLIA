import { useCallback, useEffect, useState } from "react";

import {
  getSchedule,
  putSchedule,
  type RsSchedule,
  type RsScheduleUpsert,
} from "../api/retail-sentiment";

export function useRsSchedule() {
  const [schedule, setSchedule] = useState<RsSchedule | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSchedule()
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

  const save = useCallback(async (payload: RsScheduleUpsert) => {
    const updated = await putSchedule(payload);
    setSchedule(updated);
    return updated;
  }, []);

  return { schedule, loading, error, save };
}
