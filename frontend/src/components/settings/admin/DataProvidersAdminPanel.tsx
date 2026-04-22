import { useEffect, useState } from 'react';

interface ProviderSummary {
  id: string;
  kind: 'builtin' | 'mcp' | 'openapi';
  label: string;
  domains: string[];
  enabled: boolean;
  healthy: boolean | null;
}

export function DataProvidersAdminPanel(): JSX.Element {
  const [items, setItems] = useState<ProviderSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch('/api/data-providers', { credentials: 'same-origin' });
        if (!r.ok) throw new Error('Failed to load providers');
        const j = await r.json();
        setItems(j.items ?? []);
      } catch (e) {
        setError((e as Error).message);
      }
    })();
  }, []);

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">Data providers</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Built-in, MCP, and OpenAPI providers available to all users.
        </p>
      </header>

      {error ? (
        <div role="alert" className="rounded-md border border-feedback-error/30 bg-feedback-error/10 px-3 py-2 text-sm text-feedback-error">
          {error}
        </div>
      ) : null}

      <div className="space-y-2">
        {items === null ? (
          <p className="text-sm text-text-secondary">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-text-secondary">No providers configured yet.</p>
        ) : (
          <ul className="divide-y divide-border-subtle rounded-md border border-border-subtle">
            {items.map((p) => (
              <li key={p.id} className="flex items-center justify-between px-3 py-2 text-sm">
                <div>
                  <div className="font-medium text-text-primary">{p.label}</div>
                  <div className="text-xs text-text-secondary">{p.kind} · {p.domains.join(', ')}</div>
                </div>
                <span className={`text-xs ${p.enabled ? 'text-text-primary' : 'text-text-secondary'}`}>
                  {p.enabled ? 'enabled' : 'disabled'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
      <p className="text-xs text-text-tertiary">
        Add, edit, and reorder actions are not yet wired up in this panel. Use the setup wizard.
      </p>
    </div>
  );
}
