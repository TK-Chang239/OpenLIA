import { useState } from 'react';
import type { JSX } from 'react';
import type { Proposal } from '../../api/graph';

interface Props {
  proposal: Proposal;
  onAccept: (id: string) => void;
  onDismiss: (id: string) => void;
  busy?: boolean;
}

function formatProposalSummary(p: Proposal): { primary: string; secondary: string | null } {
  const { kind, payload } = p;
  if (kind === 'user_construct') {
    const ck = typeof payload.construct_kind === 'string' ? payload.construct_kind : 'belief';
    const statement = typeof payload.statement === 'string' ? payload.statement : '(no statement)';
    const entity =
      typeof payload.entity_kind === 'string' && typeof payload.entity_value === 'string'
        ? `${payload.entity_kind}:${payload.entity_value}`
        : null;
    return { primary: statement, secondary: entity ? `${ck} on ${entity}` : ck };
  }
  if (kind === 'mention') {
    const entity =
      typeof payload.entity_kind === 'string' && typeof payload.entity_value === 'string'
        ? `${payload.entity_kind}:${payload.entity_value}`
        : '(unknown entity)';
    const artifact =
      typeof payload.artifact_kind === 'string'
        ? `${payload.artifact_kind}${payload.artifact_id ? ` · ${String(payload.artifact_id)}` : ''}`
        : '';
    return { primary: `Mention of ${entity}`, secondary: artifact || null };
  }
  return { primary: kind, secondary: null };
}

export function ProposalCard({ proposal, onAccept, onDismiss, busy }: Props): JSX.Element {
  const [showExcerpt, setShowExcerpt] = useState(false);
  const { primary, secondary } = formatProposalSummary(proposal);
  const excerpt =
    typeof proposal.payload.source_excerpt === 'string' ? proposal.payload.source_excerpt : null;
  const createdAt = new Date(proposal.created_at);

  return (
    <article
      data-testid="proposal-card"
      data-proposal-id={proposal.id}
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-4"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-text-primary">{primary}</p>
          {secondary ? (
            <p className="font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
              {secondary}
            </p>
          ) : null}
        </div>
        <span className="flex-shrink-0 font-mono text-[10px] uppercase tracking-wide text-text-tertiary">
          {createdAt.toLocaleDateString()}
        </span>
      </header>

      {excerpt ? (
        <div>
          <button
            type="button"
            className="font-mono text-[11px] uppercase tracking-wide text-text-secondary hover:text-text-primary"
            aria-expanded={showExcerpt}
            onClick={() => setShowExcerpt((v) => !v)}
          >
            {showExcerpt ? 'Hide source' : 'Show source'}
          </button>
          {showExcerpt ? (
            <blockquote
              data-testid="proposal-source-excerpt"
              className="mt-2 border-l-2 border-border-subtle pl-3 text-sm italic text-text-secondary"
            >
              {excerpt}
            </blockquote>
          ) : null}
        </div>
      ) : null}

      <footer className="flex items-center gap-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => onAccept(proposal.id)}
          className="rounded-md border border-accent-primary bg-accent-primary/10 px-3 py-1 text-sm font-medium text-accent-primary hover:bg-accent-primary/20 disabled:opacity-50"
        >
          Accept
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDismiss(proposal.id)}
          className="rounded-md border border-border-subtle px-3 py-1 text-sm text-text-primary hover:bg-surface-hover disabled:opacity-50"
        >
          Dismiss
        </button>
      </footer>
    </article>
  );
}
