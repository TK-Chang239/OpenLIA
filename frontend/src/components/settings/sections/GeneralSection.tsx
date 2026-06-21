import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  getPrefs,
  updatePrefs,
  Prefs,
  Theme,
  ApiError,
  type LangCode,
  type UiLangCode,
} from '../../../api/settings';
import { setUiLanguage } from '../../../i18n';
import { useDirtyForm } from '../useDirtyForm';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { ToggleSwitch } from '../ToggleSwitch';
import { InlineFeedback } from '../InlineFeedback';

const THEMES: Theme[] = ['system', 'light', 'dark'];

const UI_LANGUAGES: { code: UiLangCode; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-TW', label: '繁體中文 (Traditional Chinese)' },
];

const REPORT_LANGUAGES: { code: LangCode; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-TW', label: '繁體中文 (Traditional Chinese)' },
  { code: 'both', label: 'Both (English + 繁體中文)' },
];

const EMPTY: Prefs = {
  display_name: '',
  theme: 'system',
  notify_inapp: true,
  notify_email: false,
  display_language: 'en',
  response_language: 'en',
  report_language: 'en',
  timezone: 'UTC',
  timezone_source: 'auto',
  graph_extraction_time: '03:00',
};

export function GeneralSection(): JSX.Element {
  const { t } = useTranslation();
  const form = useDirtyForm<Prefs>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [saveState, setSaveState] = useState<SaveState>('idle');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    getPrefs()
      .then((p) => {
        if (!mounted) return;
        form.setValues(p);
        setLoading(false);
      })
      .catch((e: ApiError) => {
        if (!mounted) return;
        setError(e.message);
        setLoading(false);
      });
    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!loading) {
      form.markSaved();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const save = async () => {
    setSaveState('saving');
    setError(null);
    try {
      const patch = {
        display_name: form.values.display_name,
        theme: form.values.theme,
        notify_inapp: form.values.notify_inapp,
        notify_email: form.values.notify_email,
        display_language: form.values.display_language,
        response_language: form.values.response_language,
        report_language: form.values.report_language,
      };
      const next = await updatePrefs(patch);
      form.setValues(next);
      form.markSaved();
      // Reflect the chosen system language immediately so the rest of
      // the page (and the sidebar, welcome screens, etc.) re-render
      // without waiting for a refresh.
      if (next.display_language === 'zh-TW' || next.display_language === 'en') {
        setUiLanguage(next.display_language);
      }
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
      setSaveState('error');
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">{t('common.loading')}</p>;

  const themeLabels: Record<Theme, string> = {
    system: t('settings.general.theme_system'),
    light: t('settings.general.theme_light'),
    dark: t('settings.general.theme_dark'),
  };

  const reportLangLabels: Record<LangCode, string> = {
    en: t('settings.general.language_option_en'),
    'zh-TW': t('settings.general.language_option_zh_tw'),
    both: t('settings.general.language_option_both'),
  };

  return (
    <div className="max-w-2xl space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">{t('settings.general.title')}</h1>
        <SaveButton state={saveState} isDirty={form.isDirty} onClick={save} />
      </header>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <SettingGroup
        title={t('settings.general.profile_title')}
        description={t('settings.general.profile_description')}
      >
        <label className="block">
          <span className="block text-sm font-medium text-text-primary">
            {t('settings.general.display_name')}
          </span>
          <input
            type="text"
            value={form.values.display_name}
            onChange={(e) => form.setField('display_name', e.target.value)}
            maxLength={80}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          />
        </label>
      </SettingGroup>

      <SettingGroup
        title={t('settings.general.notifications_title')}
        description={t('settings.general.notifications_description')}
      >
        <ToggleSwitch
          label={t('settings.general.notify_inapp')}
          checked={form.values.notify_inapp}
          onChange={(v) => form.setField('notify_inapp', v)}
        />
        <ToggleSwitch
          label={t('settings.general.notify_email')}
          description={t('settings.general.notify_email_hint')}
          checked={form.values.notify_email}
          onChange={(v) => form.setField('notify_email', v)}
        />
      </SettingGroup>

      <SettingGroup title={t('settings.general.appearance_title')}>
        <div role="radiogroup" aria-label={t('settings.general.appearance_title')} className="flex gap-2">
          {THEMES.map((th) => (
            <label
              key={th}
              className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm ${
                form.values.theme === th
                  ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                  : 'border-border-subtle text-text-primary hover:bg-surface-hover'
              }`}
            >
              <input
                type="radio"
                name="theme"
                value={th}
                checked={form.values.theme === th}
                onChange={() => form.setField('theme', th)}
                className="sr-only"
              />
              {themeLabels[th]}
            </label>
          ))}
        </div>
      </SettingGroup>

      <SettingGroup
        title={t('settings.general.language_title')}
        description={t('settings.general.language_description')}
      >
        <label className="block">
          <span className="block text-sm font-medium text-text-primary">
            {t('settings.general.language_system_label')}
          </span>
          <span className="block text-xs text-text-secondary">
            {t('settings.general.language_system_hint')}
          </span>
          <select
            value={form.values.display_language}
            onChange={(e) => form.setField('display_language', e.target.value as UiLangCode)}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          >
            {UI_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {reportLangLabels[l.code]}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-text-primary">
            {t('settings.general.language_chat_label')}
          </span>
          <span className="block text-xs text-text-secondary">
            {t('settings.general.language_chat_hint')}
          </span>
          <select
            value={form.values.response_language}
            onChange={(e) => form.setField('response_language', e.target.value as UiLangCode)}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          >
            {UI_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {reportLangLabels[l.code]}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="block text-sm font-medium text-text-primary">
            {t('settings.general.language_report_label')}
          </span>
          <span className="block text-xs text-text-secondary">
            {t('settings.general.language_report_hint')}
          </span>
          <select
            value={form.values.report_language}
            onChange={(e) => form.setField('report_language', e.target.value as LangCode)}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          >
            {REPORT_LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {reportLangLabels[l.code]}
              </option>
            ))}
          </select>
        </label>
      </SettingGroup>
    </div>
  );
}
