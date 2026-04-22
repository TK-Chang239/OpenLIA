import React, { useEffect, useState } from 'react';
import { ApiError, createInvite, InviteSummary, listInvites, revokeInvite } from '../../../api/admin';
import { OneTimeSecretModal } from '../OneTimeSecretModal';
import { InlineFeedback } from '../InlineFeedback';

export function InvitesPanel(): JSX.Element {
  const [items, setItems] = useState<InviteSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [tokenModal, setTokenModal] = useState<string | null>(null);

  const [label, setLabel] = useState('');
  const [maxUses, setMaxUses] = useState(1);
  const [expiresAt, setExpiresAt] = useState('');
  const [creating, setCreating] = useState(false);

  const refresh = async () => {
    try {
      const r = await listInvites();
      setItems(r);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const submit = async () => {
    setCreating(true);
    setError(null);
    try {
      const r = await createInvite({
        label: label || null,
        max_uses: maxUses,
        expires_at: expiresAt ? new Date(expiresAt).toISOString() : null,
      });
      setTokenModal(r.token);
      setShowForm(false);
      setLabel('');
      setMaxUses(1);
      setExpiresAt('');
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setCreating(false);
    }
  };

  const revoke = async (id: string) => {
    if (!window.confirm('Revoke this invite? It will no longer work.')) return;
    try {
      await revokeInvite(id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold text-text-primary">Invites</h2>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
        >
          {showForm ? 'Cancel' : 'New invite'}
        </button>
      </div>

      <InlineFeedback kind={error ? 'error' : null} message={error ?? ''} />

      {showForm ? (
        <div className="rounded-md border border-border-subtle bg-bg-base p-4 space-y-3">
          <label className="block text-sm">
            <span className="block font-medium text-text-primary">Label (optional)</span>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-text-primary"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block text-sm">
              <span className="block font-medium text-text-primary">Max uses</span>
              <input
                type="number"
                min={1}
                max={999}
                value={maxUses}
                onChange={(e) => setMaxUses(Number(e.target.value))}
                className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-text-primary"
              />
            </label>
            <label className="block text-sm">
              <span className="block font-medium text-text-primary">Expires at (optional)</span>
              <input
                type="datetime-local"
                value={expiresAt}
                onChange={(e) => setExpiresAt(e.target.value)}
                className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-3 py-1.5 text-text-primary"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={submit}
            disabled={creating}
            className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 hover:bg-accent-hover"
          >
            {creating ? 'Creating...' : 'Create invite'}
          </button>
        </div>
      ) : null}

      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Uses</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {items === null ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">Loading...</td></tr>
            ) : items.length === 0 ? (
              <tr><td colSpan={5} className="px-3 py-4 text-text-secondary">No invites yet.</td></tr>
            ) : (
              items.map((inv) => (
                <tr key={inv.id} className="border-t border-border-subtle">
                  <td className="px-3 py-2 text-text-primary">{inv.label ?? '—'}</td>
                  <td className="px-3 py-2 text-text-primary">{inv.use_count} / {inv.max_uses ?? 'unlimited'}</td>
                  <td className="px-3 py-2 text-text-secondary">
                    {inv.expires_at ? new Date(inv.expires_at).toLocaleString() : 'Never'}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                      inv.revoked_at
                        ? 'bg-feedback-error/10 text-feedback-error'
                        : 'bg-feedback-success/10 text-feedback-success'
                    }`}>
                      {inv.revoked_at ? 'Revoked' : 'Active'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {inv.revoked_at === null ? (
                      <button
                        type="button"
                        onClick={() => revoke(inv.id)}
                        className="text-sm text-feedback-error hover:underline"
                      >
                        Revoke
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <OneTimeSecretModal
        open={tokenModal !== null}
        title="Invite token"
        secret={tokenModal ?? ''}
        description="Share this token through a secure channel. You will not be able to see it again."
        onClose={() => setTokenModal(null)}
      />
    </div>
  );
}
