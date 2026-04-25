import { useCallback, useEffect, useRef, useState } from "react";
import {
  getUnread,
  markRead as markReadApi,
  type UnreadResponse,
} from "../../api/notifications";
import { ApiError } from "../../api/client";

export const NOTIFICATION_POLL_MS = 60_000;

export interface NotificationPollResult {
  unreadByDepartment: Record<string, number>;
  markRead: (department: string) => Promise<void>;
  refresh: () => Promise<void>;
  error: "unauthorized" | null;
}

export function useNotificationPoll(): NotificationPollResult {
  const [state, setState] = useState<Record<string, number>>({});
  const [error, setError] = useState<"unauthorized" | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const stopped = useRef<boolean>(false);

  const apply = useCallback((resp: UnreadResponse) => {
    setState(resp.by_department);
  }, []);

  const clearTimer = useCallback((): void => {
    if (timer.current !== null) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    if (stopped.current) return;
    try {
      const resp = await getUnread();
      apply(resp);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        stopped.current = true;
        clearTimer();
        setError("unauthorized");
        return;
      }
      // swallow other errors — next tick will try again
    }
  }, [apply, clearTimer]);

  const markRead = useCallback(
    async (department: string): Promise<void> => {
      if (stopped.current) return;
      try {
        await markReadApi(department);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          stopped.current = true;
          clearTimer();
          setError("unauthorized");
          return;
        }
      }
      await refresh();
    },
    [refresh, clearTimer],
  );

  useEffect(() => {
    let cancelled = false;
    stopped.current = false;

    const tick = async (): Promise<void> => {
      await refresh();
      if (cancelled || stopped.current) return;
      timer.current = setTimeout(tick, NOTIFICATION_POLL_MS);
    };

    void tick();

    return () => {
      cancelled = true;
      stopped.current = true;
      clearTimer();
    };
  }, [refresh, clearTimer]);

  return { unreadByDepartment: state, markRead, refresh, error };
}
