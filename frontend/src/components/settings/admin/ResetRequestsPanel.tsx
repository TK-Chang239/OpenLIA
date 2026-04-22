import React, { useEffect, useState } from 'react';
import { ApiError, approveResetRequest, listResetRequests, rejectResetRequest, ResetRequestRow } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

export function ResetRequestsPanel(): JSX.Element {
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
    if (!window.confirm(`Approve password reset for ${userId}? A single-use 24h token will be generated.`)) return;
    try {
      const r = await approveResetRequest(id);
      setResetLink(r.reset_token);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const reject = async (id: string, userId: string) => {
    if (!window.confirm(`Reject password reset for ${userId}?`)) return;
    try {
      await rejectResetRequest(id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="text-base font-semibold text-text-primary">Pending password reset requests</h2>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">User</th>
              <th className="px-3 py-2">Requested</th>
              <th className="px-3 py-2">IP</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">No pending requests.</td></tr>
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
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => reject(r.id, r.user_id)}
                        className="text-sm text-feedback-error hover:underline"
                      >
                        Reject
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
        title="Password reset token"
        secret={resetLink ?? ''}
        description="Share with the user through a secure channel. Valid for 24 hours, single-use."
        onClose={() => setResetLink(null)}
      />
    </div>
  );
}
