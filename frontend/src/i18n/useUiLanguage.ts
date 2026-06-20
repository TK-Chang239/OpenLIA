import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { getPrefs } from '../api/settings';
import { setUiLanguage, type SupportedLanguage } from './index';

/**
 * Pull the user's `display_language` from prefs and push it into i18next.
 *
 * Re-runs whenever auth becomes ready or the signed-in user changes, not just
 * once on mount: a cold load lands on the login screen (unauthenticated), where
 * `getPrefs` 401s and the browser-detected language stays in place. Without the
 * `authReady`/`userKey` dependencies, an SPA login would never re-sync and the
 * UI would stay in the browser language even though the user's pref says
 * otherwise. Settings-page saves still call setUiLanguage() directly.
 */
export function useUiLanguageSync(authReady: boolean, userKey: string): void {
  useEffect(() => {
    if (!authReady) return;
    let cancelled = false;
    getPrefs()
      .then((p) => {
        if (cancelled) return;
        const lng = p.display_language === 'zh-TW' ? 'zh-TW' : 'en';
        setUiLanguage(lng as SupportedLanguage);
      })
      .catch(() => {
        // Pref fetch failed (transient/unauthenticated) — leave the current
        // language in place; the layout still works.
      });
    return () => {
      cancelled = true;
    };
  }, [authReady, userKey]);
}

export { useTranslation };
