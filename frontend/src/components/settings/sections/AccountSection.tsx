import React, { useEffect, useState } from 'react';
import { getPrefs, updateEmail, updatePrefs, type LangCode } from '../../../api/settings';
import { ChangePasswordForm } from '../../auth/ChangePasswordForm';
import { SessionsPanel } from '../../auth/SessionsPanel';

interface Props {
  currentEmail: string;
  mustChangePassword: boolean;
}

const LANGUAGES: { code: LangCode; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-Hant', label: 'Traditional Chinese' },
  { code: 'zh-Hans', label: 'Simplified Chinese' },
];

export function AccountSection({ currentEmail, mustChangePassword }: Props): JSX.Element {
  const [newEmail, setNewEmail] = useState(currentEmail);
  const [currentPassword, setCurrentPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');

  const [displayLanguage, setDisplayLanguage] = useState<LangCode>('en');
  const [responseLanguage, setResponseLanguage] = useState<LangCode>('en');
  const [reportLanguage, setReportLanguage] = useState<LangCode>('en');
  const [langError, setLangError] = useState('');
  const [langSuccess, setLangSuccess] = useState('');

  useEffect(() => {
    getPrefs().then((prefs) => {
      setDisplayLanguage(prefs.display_language);
      setResponseLanguage(prefs.response_language);
      setReportLanguage(prefs.report_language);
    });
  }, []);

  async function handleEmailChange(e: React.FormEvent) {
    e.preventDefault();
    setEmailError('');
    setEmailSuccess('');
    try {
      await updateEmail({ new_email: newEmail, current_password: currentPassword });
      setEmailSuccess('Email updated.');
      setCurrentPassword('');
    } catch (err: unknown) {
      setEmailError(err instanceof Error ? err.message : 'Failed to update email.');
    }
  }

  async function handleSaveLanguages(e: React.FormEvent) {
    e.preventDefault();
    setLangError('');
    setLangSuccess('');
    try {
      await updatePrefs({
        display_language: displayLanguage,
        response_language: responseLanguage,
        report_language: reportLanguage,
      });
      setLangSuccess('Languages saved.');
    } catch (err: unknown) {
      setLangError(err instanceof Error ? err.message : 'Failed to save languages.');
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {mustChangePassword && (
        <div role="alert" className="rounded border border-feedback-error/30 bg-feedback-error/10 px-4 py-3 text-feedback-error">
          You must change your password before continuing.
        </div>
      )}

      {/* Email change */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">Change Email</h2>
        <form onSubmit={handleEmailChange} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="new-email" className="text-sm text-text-secondary">
              New email
            </label>
            <input
              id="new-email"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
              aria-label="New email"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="current-password-email" className="text-sm text-text-secondary">
              Current password
            </label>
            <input
              id="current-password-email"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
              aria-label="Current password"
            />
          </div>
          {emailError && <p className="text-sm text-feedback-error">{emailError}</p>}
          {emailSuccess && <p className="text-sm text-text-secondary">{emailSuccess}</p>}
          <button
            type="submit"
            className="self-start rounded bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Change email
          </button>
        </form>
      </section>

      {/* Change password */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">Change Password</h2>
        <ChangePasswordForm />
      </section>

      {/* Language preferences */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">Language Preferences</h2>
        <form onSubmit={handleSaveLanguages} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="display-language" className="text-sm text-text-secondary">
              Display language
            </label>
            <select
              id="display-language"
              value={displayLanguage}
              onChange={(e) => setDisplayLanguage(e.target.value as LangCode)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="response-language" className="text-sm text-text-secondary">
              Response language
            </label>
            <select
              id="response-language"
              value={responseLanguage}
              onChange={(e) => setResponseLanguage(e.target.value as LangCode)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="report-language" className="text-sm text-text-secondary">
              Report language
            </label>
            <select
              id="report-language"
              value={reportLanguage}
              onChange={(e) => setReportLanguage(e.target.value as LangCode)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
          {langError && <p className="text-sm text-feedback-error">{langError}</p>}
          {langSuccess && <p className="text-sm text-text-secondary">{langSuccess}</p>}
          <button
            type="submit"
            className="self-start rounded bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            Save languages
          </button>
        </form>
      </section>

      {/* Sessions */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">Active Sessions</h2>
        <SessionsPanel />
      </section>
    </div>
  );
}
