import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from './locales/en.json';
import zhTW from './locales/zh-TW.json';

export type SupportedLanguage = 'en' | 'zh-TW';

const STORAGE_KEY = 'openlia.displayLanguage';

export function detectInitialLanguage(): SupportedLanguage {
  if (typeof window === 'undefined') return 'en';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'en' || stored === 'zh-TW') return stored;
  // No explicit choice yet (e.g. the pre-login screen): default to English
  // rather than auto-detecting navigator.language. This keeps the
  // unauthenticated experience English-first. Signed-in users still get their
  // saved display_language, and any explicit choice persists via localStorage.
  return 'en';
}

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    'zh-TW': { translation: zhTW },
  },
  lng: detectInitialLanguage(),
  fallbackLng: 'en',
  interpolation: { escapeValue: false },
  returnNull: false,
});

export function setUiLanguage(lng: SupportedLanguage): void {
  if (lng !== i18n.language) {
    void i18n.changeLanguage(lng);
  }
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, lng);
    document.documentElement.lang = lng === 'zh-TW' ? 'zh-Hant-TW' : 'en';
    document.documentElement.dataset.lang = lng;
  }
}

if (typeof document !== 'undefined') {
  document.documentElement.lang = i18n.language === 'zh-TW' ? 'zh-Hant-TW' : 'en';
  document.documentElement.dataset.lang = i18n.language;
}

export default i18n;
