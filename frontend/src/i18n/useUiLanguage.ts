import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { getPrefs } from '../api/settings';
import { setUiLanguage, type SupportedLanguage } from './index';

/**
 * Pull the user's `display_language` from prefs once on mount and push
 * it into i18next. Subsequent settings-page saves call setUiLanguage()
 * directly, so this hook only handles the cold-start sync.
 */
export function useUiLanguageSync(): void {
  useEffect(() => {
    let cancelled = false;
    getPrefs()
      .then((p) => {
        if (cancelled) return;
        const lng = p.display_language === 'zh-TW' ? 'zh-TW' : 'en';
        setUiLanguage(lng as SupportedLanguage);
      })
      .catch(() => {
        // Unauthenticated cold start (login screen) — leave the
        // browser-detected language in place; the layout still works.
      });
    return () => {
      cancelled = true;
    };
  }, []);
}

export { useTranslation };
