import React, { useEffect, useState } from 'react';
import { ProviderRow } from '../../../setup/steps/ProviderRow';
import { AddProviderForm } from '../../../setup/steps/AddProviderForm';

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
  const [showForm, setShowForm] = useState(false);

  const refresh = async () => {
    try {
      const r = await fetch('/api/data-providers', { credentials: 'same-origin' });
      if (!r.ok) throw new Error('Failed to load providers');
      const j = await r.json();
      setItems(j.items ?? []);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => { refresh(); }, []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Data providers</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Built-in, MCP, and OpenAPI providers available to all users.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"
        >
          {showForm ? 'Cancel' : 'Add provider'}
        </button>
      </div>

      {error ? (
        <div role="alert" className="rounded-md border border-feedback-error/30 bg-feedback-error/10 px-3 py-2 text-sm text-feedback-error">
          {error}
        </div>
      ) : null}

      {showForm ? (
        <AddProviderForm
          onCreated={() => {
            setShowForm(false);
            refresh();
          }}
        />
      ) : null}

      <div className="space-y-2">
        {items === null ? (
          <p className="text-sm text-text-secondary">Loading...</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-text-secondary">No providers configured yet.</p>
        ) : (
          items.map((p) => <ProviderRow key={p.id} provider={p} onChange={refresh} />)
        )}
      </div>
    </div>
  );
}
