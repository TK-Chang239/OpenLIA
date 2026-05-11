import { useState } from 'react';
import type { JSX } from 'react';
import type { Construct } from '../../api/graph';

interface Props {
  construct: Construct;
  onDelete: (id: string) => void;
  busy?: boolean;
}

export function ConstructCard({ construct, onDelete, busy }: Props): JSX.Element {
  const [showWhy, setShowWhy] = useState(false);
  const createdAt = new Date(construct.created_at);
  const excerpt = construct.provenance?.source_excerpt ?? null;

  return (
    <article
      data-testid="construct-card"
      data-construct-id={construct.id}
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-4"
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm text-text-primary">{construct.statement}</p>
          <p className="font-mono text-[11px] uppercase tracking-wide text-text-tertiary">
            {construct.kind}
            <span className="mx-1 text-border-subtle">·</span>
            anchored {createdAt.toLocaleDateString()}
          </p>
        </div>
        <button
          type="button"
          disabled={busy}
          onClick={() => onDelete(construct.id)}
          aria-label={`Delete construct ${construct.id}`}
          className="flex-shrink-0 rounded-md border border-border-subtle px-2 py-1 font-mono text-[11px] uppercase tracking-wide text-text-secondary hover:text-feedback-error disabled:opacity-50"
        >
          Delete
        </button>
      </header>

      {excerpt ? (
        <div>
          <button
            type="button"
            className="font-mono text-[11px] uppercase tracking-wide text-text-secondary hover:text-text-primary"
            aria-expanded={showWhy}
            onClick={() => setShowWhy((v) => !v)}
          >
            {showWhy ? 'Hide why' : 'Why?'}
          </button>
          {showWhy ? (
            <blockquote
              data-testid="construct-source-excerpt"
              className="mt-2 border-l-2 border-border-subtle pl-3 text-sm italic text-text-secondary"
            >
              {excerpt}
            </blockquote>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
