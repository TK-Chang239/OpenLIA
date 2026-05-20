import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { updateEmail } from '../../../api/settings';
import { ChangePasswordForm } from '../../auth/ChangePasswordForm';
import { SessionsPanel } from '../../auth/SessionsPanel';

interface Props {
  currentEmail: string;
  mustChangePassword: boolean;
}

export function AccountSection({ currentEmail, mustChangePassword }: Props): JSX.Element {
  const { t } = useTranslation();
  const [newEmail, setNewEmail] = useState(currentEmail);
  const [currentPassword, setCurrentPassword] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailSuccess, setEmailSuccess] = useState('');

  async function handleEmailChange(e: React.FormEvent) {
    e.preventDefault();
    setEmailError('');
    setEmailSuccess('');
    try {
      await updateEmail({ new_email: newEmail, current_password: currentPassword });
      setEmailSuccess(t('settings.account.email_updated'));
      setCurrentPassword('');
    } catch (err: unknown) {
      setEmailError(err instanceof Error ? err.message : t('settings.account.change_email_failed'));
    }
  }

  return (
    <div className="flex flex-col gap-8">
      {mustChangePassword && (
        <div role="alert" className="rounded border border-feedback-error/30 bg-feedback-error/10 px-4 py-3 text-feedback-error">
          {t('settings.account.must_change_password_banner')}
        </div>
      )}

      {/* Email change */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">{t('settings.account.email_section_title')}</h2>
        <form onSubmit={handleEmailChange} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="new-email" className="text-sm text-text-secondary">
              {t('settings.account.new_email')}
            </label>
            <input
              id="new-email"
              type="email"
              value={newEmail}
              onChange={(e) => setNewEmail(e.target.value)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
              aria-label={t('settings.account.new_email')}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="current-password-email" className="text-sm text-text-secondary">
              {t('settings.account.current_password')}
            </label>
            <input
              id="current-password-email"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              className="rounded border border-border-subtle bg-bg-elevated px-3 py-2 text-text-primary focus:border-border-secondary focus:outline-none"
              aria-label={t('settings.account.current_password')}
            />
          </div>
          {emailError && <p className="text-sm text-feedback-error">{emailError}</p>}
          {emailSuccess && <p className="text-sm text-text-secondary">{emailSuccess}</p>}
          <button
            type="submit"
            className="self-start rounded bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"
          >
            {t('settings.account.change_email_button')}
          </button>
        </form>
      </section>

      {/* Change password */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">{t('settings.account.change_password_section_title')}</h2>
        <ChangePasswordForm />
      </section>

      {/* Sessions */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">{t('settings.account.active_sessions_section_title')}</h2>
        <SessionsPanel />
      </section>
    </div>
  );
}
