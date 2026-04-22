import React, { useEffect, useState } from 'react';
import { getPrefs, updatePrefs, Prefs, Theme, ApiError } from '../../../api/settings';
import { useDirtyForm } from '../useDirtyForm';
import { SaveButton, SaveState } from '../SaveButton';
import { SettingGroup } from '../SettingGroup';
import { ToggleSwitch } from '../ToggleSwitch';
import { InlineFeedback } from '../InlineFeedback';

const THEMES: Theme[] = ['system', 'light', 'dark'];

const EMPTY: Prefs = {
  display_name: '',
  theme: 'system',
  notify_inapp: true,
  notify_email: false,
  display_language: 'en',
  response_language: 'en',
  report_language: 'en',
};

export function GeneralSection(): JSX.Element {
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
      };
      const next = await updatePrefs(patch);
      form.setValues(next);
      form.markSaved();
      setSaveState('saved');
      setTimeout(() => setSaveState('idle'), 1500);
    } catch (e) {
      const err = e as ApiError;
      setError(err.message);
      setSaveState('error');
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="max-w-2xl space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text-primary">General</h1>
        <SaveButton state={saveState} isDirty={form.isDirty} onClick={save} />
      </header>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <SettingGroup title="Profile" description="Name shown in the sidebar and reports.">
        <label className="block">
          <span className="block text-sm font-medium text-text-primary">Display name</span>
          <input
            type="text"
            value={form.values.display_name}
            onChange={(e) => form.setField('display_name', e.target.value)}
            maxLength={80}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-sm text-text-primary focus:border-border-secondary focus:outline-none"
          />
        </label>
      </SettingGroup>

      <SettingGroup title="Notifications" description="Alerts when reports and scheduled jobs finish.">
        <ToggleSwitch
          label="In-app notifications"
          checked={form.values.notify_inapp}
          onChange={(v) => form.setField('notify_inapp', v)}
        />
        <ToggleSwitch
          label="Email notifications"
          description="Requires SMTP setup by an admin."
          checked={form.values.notify_email}
          onChange={(v) => form.setField('notify_email', v)}
        />
      </SettingGroup>

      <SettingGroup title="Appearance">
        <div role="radiogroup" aria-label="Theme" className="flex gap-2">
          {THEMES.map((t) => (
            <label
              key={t}
              className={`cursor-pointer rounded-md border px-3 py-1.5 text-sm ${
                form.values.theme === t
                  ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                  : 'border-border-subtle text-text-primary hover:bg-surface-hover'
              }`}
            >
              <input
                type="radio"
                name="theme"
                value={t}
                checked={form.values.theme === t}
                onChange={() => form.setField('theme', t)}
                className="sr-only"
              />
              {t[0].toUpperCase() + t.slice(1)}
            </label>
          ))}
        </div>
      </SettingGroup>
    </div>
  );
}
