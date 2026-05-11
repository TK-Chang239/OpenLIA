import { useEffect, useRef } from 'react';
import { useAuth } from './AuthContext';
import { updateTimezone } from '../api/settings';

/**
 * Captures the browser's IANA timezone on every successful auth and fires
 * `PUT /api/settings/timezone` with `source: "auto"`. The backend ignores
 * auto writes when the stored source is `manual`, so re-running on every
 * login is safe.
 *
 * Fires once per `user.id` per app load.
 */
export function useTimezoneAutoCapture(): void {
  const { status, user } = useAuth();
  const firedFor = useRef<string | null>(null);

  useEffect(() => {
    if (status !== 'authenticated' && status !== 'personal') return;
    if (!user) return;
    if (firedFor.current === user.id) return;
    firedFor.current = user.id;

    let timezone: string;
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return;
    }
    if (!timezone) return;

    void updateTimezone({ timezone, source: 'auto' }).catch((err) => {
      // Auto-capture is best-effort; never block the UI.
      // eslint-disable-next-line no-console
      console.warn('timezone auto-capture failed', err);
    });
  }, [status, user]);
}
