import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  adminResetPassword,
  AdminUserRow,
  ApiError,
  disableUser,
  enableUser,
  listAdminUsers,
} from '../../../api/admin';
import { InlineFeedback } from '../InlineFeedback';
import { OneTimeSecretModal } from '../OneTimeSecretModal';

interface Props {
  currentUserId: string;
}

export function UsersPanel({ currentUserId }: Props): JSX.Element {
  const { t } = useTranslation();
  const [items, setItems] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tempPassword, setTempPassword] = useState<string | null>(null);
  const [tempPasswordEmail, setTempPasswordEmail] = useState<string>('');

  const refresh = async () => {
    try {
      const r = await listAdminUsers();
      setItems(r);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const toggle = async (u: AdminUserRow) => {
    const confirmMsg = u.is_disabled
      ? t('settings.users.confirm_toggle_enable', { email: u.email })
      : t('settings.users.confirm_toggle_disable', { email: u.email });
    if (!window.confirm(confirmMsg)) return;
    try {
      if (u.is_disabled) await enableUser(u.id);
      else await disableUser(u.id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reset = async (u: AdminUserRow) => {
    if (!window.confirm(t('settings.users.confirm_reset', { email: u.email }))) return;
    try {
      const result = await adminResetPassword(u.id);
      setTempPassword(result.temporary_password);
      setTempPasswordEmail(u.email);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-text-primary">{t('settings.users.title')}</h2>
      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />
      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">{t('settings.users.col_email')}</th>
              <th className="px-3 py-2">{t('settings.users.col_name')}</th>
              <th className="px-3 py-2">{t('settings.users.col_role')}</th>
              <th className="px-3 py-2">{t('settings.users.col_status')}</th>
              <th className="px-3 py-2">{t('settings.users.col_last_login')}</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-text-secondary">
                  {t('settings.users.loading')}
                </td>
              </tr>
            ) : (
              items.map((u) => (
                <tr key={u.id} className="border-t border-border-subtle">
                  <td className="px-3 py-2 text-text-primary">{u.email}</td>
                  <td className="px-3 py-2 text-text-primary">{u.display_name}</td>
                  <td className="px-3 py-2 text-text-primary">{u.is_admin ? t('settings.users.role_admin') : t('settings.users.role_user')}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.is_disabled
                          ? 'bg-feedback-error/10 text-feedback-error'
                          : 'bg-feedback-success/10 text-feedback-success'
                      }`}
                    >
                      {u.is_disabled ? t('settings.users.status_disabled') : t('settings.users.status_enabled')}
                    </span>
                    {u.must_change_password ? (
                      <span className="ml-1 inline-block rounded-full bg-feedback-warning/10 px-2 py-0.5 text-xs font-medium text-feedback-warning">
                        {t('settings.users.must_change_pw')}
                      </span>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-text-secondary">
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : '—'}
                  </td>
                  <td className="px-3 py-2 text-right space-x-3">
                    {u.id !== currentUserId ? (
                      <>
                        <button
                          type="button"
                          data-action="reset"
                          onClick={() => reset(u)}
                          className="text-sm text-accent-primary hover:underline"
                        >
                          {t('settings.users.reset_password')}
                        </button>
                        <button
                          type="button"
                          data-action="disable"
                          onClick={() => toggle(u)}
                          className={`text-sm ${
                            u.is_disabled ? 'text-feedback-success' : 'text-feedback-error'
                          } hover:underline`}
                        >
                          {u.is_disabled ? t('settings.users.enable') : t('settings.users.disable')}
                        </button>
                      </>
                    ) : (
                      <span className="text-xs text-text-secondary">{t('settings.users.you')}</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <OneTimeSecretModal
        open={tempPassword !== null}
        title={t('settings.users.temp_password_title', { email: tempPasswordEmail })}
        secret={tempPassword ?? ''}
        description={t('settings.users.temp_password_description')}
        onClose={() => {
          setTempPassword(null);
          setTempPasswordEmail('');
        }}
      />
    </div>
  );
}
