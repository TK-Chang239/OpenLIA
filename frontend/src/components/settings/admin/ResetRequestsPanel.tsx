import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ApiError, approveResetRequest, listResetRequests, rejectResetRequest, ResetRequestRow } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

export function ResetRequestsPanel(): JSX.Element {
  const { t } = useTranslation();
  const [items, setItems] = useState<ResetRequestRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resetLink, setResetLink] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listResetRequests();
      setItems(r);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => { refresh(); }, []);

  const approve = async (id: string, userId: string) => {
    if (!window.confirm(t('settings.reset_requests.confirm_approve', { user: userId }))) return;
    try {
      const r = await approveResetRequest(id);
      setResetLink(r.reset_token);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reject = async (id: string, userId: string) => {
    if (!window.confirm(t('settings.reset_requests.confirm_reject', { user: userId }))) return;
    try {
      await rejectResetRequest(id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-text-primary">{t('settings.reset_requests.title')}</h2>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">{t('settings.reset_requests.col_user')}</th>
              <th className="px-3 py-2">{t('settings.reset_requests.col_requested')}</th>
              <th className="px-3 py-2">{t('settings.reset_requests.col_ip')}</th>
              <th className="px-3 py-2">{t('settings.reset_requests.col_status')}</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">{t('settings.reset_requests.loading')}</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">{t('settings.reset_requests.none_pending')}</td></tr>
            ) : items.map((r) => (
              <tr key={r.id} className="border-t border-border-subtle">
                <td className="px-3 py-2 text-text-primary">{r.user_id}</td>
                <td className="px-3 py-2 text-text-secondary">{new Date(r.requested_at).toLocaleString()}</td>
                <td className="px-3 py-2 text-text-secondary">{r.requested_ip ?? '—'}</td>
                <td className="px-3 py-2 text-text-primary">{r.status}</td>
                <td className="px-3 py-2 text-right space-x-3">
                  {r.status === 'pending' ? (
                    <>
                      <button
                        type="button"
                        onClick={() => approve(r.id, r.user_id)}
                        className="text-sm text-accent-primary hover:underline"
                      >
                        {t('settings.reset_requests.approve')}
                      </button>
                      <button
                        type="button"
                        onClick={() => reject(r.id, r.user_id)}
                        className="text-sm text-feedback-error hover:underline"
                      >
                        {t('settings.reset_requests.reject')}
                      </button>
                    </>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <OneTimeSecretModal
        open={resetLink !== null}
        title={t('settings.reset_requests.token_modal_title')}
        secret={resetLink ?? ''}
        description={t('settings.reset_requests.token_modal_description')}
        onClose={() => setResetLink(null)}
      />
    </div>
  );
}
