import { useCallback, useEffect, useRef, useState } from "react";
import {
  getUnread,
  markRead as markReadApi,
  type UnreadResponse,
} from "../../api/notifications";

export const NOTIFICATION_POLL_MS = 60_000;

export interface NotificationPollResult {
  unreadByDepartment: Record<string, number>;
  markRead: (department: string) => Promise<void>;
  refresh: () => Promise<void>;
}

export function useNotificationPoll(): NotificationPollResult {
  const [state, setState] = useState<Record<string, number>>({});
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const apply = useCallback((resp: UnreadResponse) => {
    setState(resp.by_department);
  }, []);

  const refresh = useCallback(async (): Promise<void> => {
    try {
      const resp = await getUnread();
      apply(resp);
    } catch {
      // swallow — next tick will try again
    }
  }, [apply]);

  const markRead = useCallback(
    async (department: string): Promise<void> => {
      try {
        await markReadApi(department);
      } catch {
        // still refresh; server is authoritative
      }
      await refresh();
    },
    [refresh],
  );

  useEffect(() => {
    let cancelled = false;

    const tick = async (): Promise<void> => {
      await refresh();
      if (cancelled) return;
      timer.current = setTimeout(tick, NOTIFICATION_POLL_MS);
    };

    void tick();

    return () => {
      cancelled = true;
      if (timer.current !== null) {
        clearTimeout(timer.current);
        timer.current = null;
      }
    };
  }, [refresh]);

  return { unreadByDepartment: state, markRead, refresh };
}
