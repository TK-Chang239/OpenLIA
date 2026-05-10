import { useCallback, useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  acceptProposal,
  dismissProposal,
  listProposals,
  type Proposal,
} from '../../api/graph';
import { ApiError } from '../../api/_request';
import { useToast } from '../primitives/Toast';
import { ProposalCard } from './ProposalCard';

export function ProposalsList(): JSX.Element {
  const [items, setItems] = useState<Proposal[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyIds, setBusyIds] = useState<ReadonlySet<string>>(new Set());
  const toast = useToast();

  useEffect(() => {
    let cancelled = false;
    setError(null);
    listProposals('pending')
      .then((r) => {
        if (cancelled) return;
        setItems(r.items);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof ApiError ? e.message : 'Failed to load proposals';
        setError(msg);
        setItems([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setBusy = useCallback((id: string, on: boolean) => {
    setBusyIds((prev) => {
      const next = new Set(prev);
      if (on) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const handleAccept = useCallback(
    async (id: string) => {
      if (items === null) return;
      const previous = items;
      const optimistic = items.filter((p) => p.id !== id);
      setItems(optimistic);
      setBusy(id, true);
      try {
        await acceptProposal(id);
      } catch (e: unknown) {
        setItems(previous);
        const msg = e instanceof ApiError ? e.message : 'Failed to accept proposal';
        toast.push({ title: msg, tone: 'error' });
      } finally {
        setBusy(id, false);
      }
    },
    [items, setBusy, toast],
  );

  const handleDismiss = useCallback(
    async (id: string) => {
      if (items === null) return;
      const previous = items;
      const optimistic = items.filter((p) => p.id !== id);
      setItems(optimistic);
      setBusy(id, true);
      try {
        await dismissProposal(id);
      } catch (e: unknown) {
        setItems(previous);
        const msg = e instanceof ApiError ? e.message : 'Failed to dismiss proposal';
        toast.push({ title: msg, tone: 'error' });
      } finally {
        setBusy(id, false);
      }
    },
    [items, setBusy, toast],
  );

  if (items === null) {
    return <p className="text-sm text-text-secondary">Loading...</p>;
  }
  if (error && items.length === 0) {
    return (
      <div
        role="alert"
        className="rounded-md border border-feedback-error/20 bg-feedback-error/10 px-3 py-2 text-sm text-feedback-error"
      >
        {error}
      </div>
    );
  }
  if (items.length === 0) {
    return (
      <p data-testid="proposals-empty" className="text-sm text-text-secondary">
        No pending proposals.
      </p>
    );
  }
  return (
    <div className="space-y-3" data-testid="proposals-list">
      {items.map((p) => (
        <ProposalCard
          key={p.id}
          proposal={p}
          onAccept={handleAccept}
          onDismiss={handleDismiss}
          busy={busyIds.has(p.id)}
        />
      ))}
    </div>
  );
}
