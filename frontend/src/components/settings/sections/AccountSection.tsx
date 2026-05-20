import React, { useState } from 'react';
import { updateEmail } from '../../../api/settings';
import { ChangePasswordForm } from '../../auth/ChangePasswordForm';
import { SessionsPanel } from '../../auth/SessionsPanel';

interface Props {
  currentEmail: string;
  mustChangePassword: boolean;
}

export function AccountSection({ currentEmail, mustChangePassword }: Props): JSX.Element {
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
      setEmailSuccess('Email updated.');
      setCurrentPassword('');
    } catch (err: unknown) {
      setEmailError(err instanceof Error ? err.message : 'Failed to update email.');
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

      {/* Sessions */}
      <section>
        <h2 className="mb-4 text-base font-semibold text-text-primary">Active Sessions</h2>
        <SessionsPanel />
      </section>
    </div>
  );
}
