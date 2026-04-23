import { useEffect, useState } from 'react';
import { adminResetPassword, AdminUserRow, ApiError, disableUser, enableUser, listAdminUsers } from '../../../api/admin';
import { InlineFeedback } from '../InlineFeedback';

interface Props {
  currentUserId: string;
}

export function UsersPanel({ currentUserId }: Props): JSX.Element {
  const [items, setItems] = useState<AdminUserRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listAdminUsers();
      setItems(r);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => { refresh(); }, []);

  const toggle = async (u: AdminUserRow) => {
    const action = u.is_disabled ? 'enable' : 'disable';
    if (!window.confirm(`${action === 'disable' ? 'Disable' : 'Enable'} ${u.email}?`)) return;
    try {
      if (u.is_disabled) await enableUser(u.id);
      else await disableUser(u.id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reset = async (u: AdminUserRow) => {
    if (!window.confirm(`Reset password for ${u.email}? They will be forced to change it on next login.`)) return;
    const newPassword = window.prompt('Enter a temporary replacement password');
    if (!newPassword) return;
    try {
      await adminResetPassword(u.id, newPassword);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-text-primary">Users</h2>
      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />
      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Role</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Last login</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={6} className="px-3 py-4 text-text-secondary">Loading...</td></tr>
            ) : items.map((u) => (
              <tr key={u.id} className="border-t border-border-subtle">
                <td className="px-3 py-2 text-text-primary">{u.email}</td>
                <td className="px-3 py-2 text-text-primary">{u.display_name}</td>
                <td className="px-3 py-2 text-text-primary">{u.is_admin ? 'admin' : 'user'}</td>
                <td className="px-3 py-2">
                  <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                    u.is_disabled
                      ? 'bg-feedback-error/10 text-feedback-error'
                      : 'bg-feedback-success/10 text-feedback-success'
                  }`}>
                    {u.is_disabled ? 'Disabled' : 'Enabled'}
                  </span>
                  {u.must_change_password ? (
                    <span className="ml-1 inline-block rounded-full bg-feedback-warning/10 px-2 py-0.5 text-xs font-medium text-feedback-warning">
                      Must change pw
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
                        Reset password
                      </button>
                      <button
                        type="button"
                        data-action="disable"
                        onClick={() => toggle(u)}
                        className={`text-sm ${u.is_disabled ? 'text-feedback-success' : 'text-feedback-error'} hover:underline`}
                      >
                        {u.is_disabled ? 'Enable' : 'Disable'}
                      </button>
                    </>
                  ) : (
                    <span className="text-xs text-text-secondary">You</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
