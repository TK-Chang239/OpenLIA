import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchDashboard,
  type DashboardPayload,
} from "../api/panic-thermometer";

export interface UsePtDashboardState {
  data: DashboardPayload | null;
  isLoading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
}

export function usePtDashboard(intervalSeconds: number | null): UsePtDashboardState {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    try {
      const payload = await fetchDashboard();
      setData(payload);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    if (intervalSeconds && intervalSeconds > 0) {
      const tick = () => {
        void refresh();
        timerRef.current = setTimeout(tick, intervalSeconds * 1000);
      };
      timerRef.current = setTimeout(tick, intervalSeconds * 1000);
    }
    return () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [intervalSeconds, refresh]);

  return { data, isLoading, error, refresh };
}
