/**
 * Admin panel for /settings/data-providers/*.
 *
 * Provides:
 *   - Provider list with category/kind/mode badges and enabled state
 *   - Inline create form (kind, label, category, mode, api_key/env_var/base_url)
 *   - Per-provider connection test (404 / 501 surfaced via InlineFeedback)
 *   - Requirement mapping table with PUT /mappings/{requirement_type}
 *   - Delete blocked when assigned (409 surfaced)
 */
import { FormEvent, useEffect, useState } from 'react';
import { ApiError } from '../../../api/_request';
import {
  DataProvider,
  DataProviderCreate,
  ProviderCategory,
  ProviderMode,
  RequirementMapping,
  createDataProvider,
  deleteDataProvider,
  listDataProviders,
  listRequirementMappings,
  setRequirementMapping,
  testDataProviderConnection,
} from '../../../api/data_providers';
import { InlineFeedback } from '../InlineFeedback';

const CATEGORIES: ProviderCategory[] = ['financial', 'news', 'social_media', 'search'];
const MODES: ProviderMode[] = ['api_key', 'mcp'];

interface CreateFormState {
  kind: string;
  label: string;
  category: ProviderCategory;
  mode: ProviderMode;
  api_key: string;
  env_var_name: string;
  base_url: string;
}

const EMPTY: CreateFormState = {
  kind: '',
  label: '',
  category: 'financial',
  mode: 'api_key',
  api_key: '',
  env_var_name: '',
  base_url: '',
};

export function DataProvidersAdminPanel(): JSX.Element {
  const [providers, setProviders] = useState<DataProvider[] | null>(null);
  const [mappings, setMappings] = useState<RequirementMapping[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState<CreateFormState>(EMPTY);
  const [submitting, setSubmitting] = useState(false);

  const refresh = async () => {
    try {
      const [{ providers: provs }, { mappings: maps }] = await Promise.all([
        listDataProviders(),
        listRequirementMappings(),
      ]);
      setProviders(provs);
      setMappings(maps);
      setError(null);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const onCreate = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const body: DataProviderCreate = {
        kind: form.kind.trim(),
        label: form.label.trim(),
        category: form.category,
        mode: form.mode,
        api_key: form.mode === 'api_key' ? form.api_key || null : null,
        env_var_name: form.env_var_name || null,
        base_url: form.base_url || null,
      };
      await createDataProvider(body);
      setForm(EMPTY);
      setShowAdd(false);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async (p: DataProvider) => {
    if (!confirm(`Delete provider ${p.label}?`)) return;
    try {
      await deleteDataProvider(p.id);
      setInfo(`Deleted ${p.label}.`);
      await refresh();
    } catch (err) {
      const e = err as ApiError;
      if (e.status === 409) {
        setError(
          `${p.label} is in use by a requirement mapping; remove the mapping before deleting.`,
        );
      } else {
        setError(e.message);
      }
    }
  };

  const onTest = async (p: DataProvider) => {
    setError(null);
    setInfo(null);
    try {
      const r = await testDataProviderConnection(p.id);
      setInfo(`${p.label}: ${r.ok ? 'connection healthy' : 'connection unhealthy'}.`);
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onAssignMapping = async (requirementType: string, providerId: string) => {
    try {
      await setRequirementMapping(requirementType, { provider_id: providerId, priority: 100 });
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">Data providers</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Built-in API-key and MCP providers available to every department.
        </p>
      </header>

      {error ? <InlineFeedback kind="error" message={error} /> : null}
      {info ? <InlineFeedback kind="success" message={info} /> : null}

      <div className="flex justify-end">
        <button
          type="button"
          onClick={() => setShowAdd((v) => !v)}
          className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover"
        >
          {showAdd ? 'Cancel' : 'Add provider'}
        </button>
      </div>

      {showAdd ? (
        <form
          onSubmit={onCreate}
          className="grid grid-cols-2 gap-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
          aria-label="Add data provider"
        >
          <label className="text-xs text-text-secondary">
            Kind
            <input
              type="text"
              required
              value={form.kind}
              onChange={(e) => setForm((s) => ({ ...s, kind: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <label className="text-xs text-text-secondary">
            Label
            <input
              type="text"
              required
              value={form.label}
              onChange={(e) => setForm((s) => ({ ...s, label: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <label className="text-xs text-text-secondary">
            Category
            <select
              value={form.category}
              onChange={(e) =>
                setForm((s) => ({ ...s, category: e.target.value as ProviderCategory }))
              }
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-text-secondary">
            Mode
            <select
              value={form.mode}
              onChange={(e) => setForm((s) => ({ ...s, mode: e.target.value as ProviderMode }))}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            >
              {MODES.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          {form.mode === 'api_key' ? (
            <>
              <label className="text-xs text-text-secondary">
                API key
                <input
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setForm((s) => ({ ...s, api_key: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <label className="text-xs text-text-secondary">
                Env var name (alt)
                <input
                  type="text"
                  value={form.env_var_name}
                  onChange={(e) => setForm((s) => ({ ...s, env_var_name: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
            </>
          ) : null}
          <label className="col-span-2 text-xs text-text-secondary">
            Base URL (optional)
            <input
              type="text"
              value={form.base_url}
              onChange={(e) => setForm((s) => ({ ...s, base_url: e.target.value }))}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <div className="col-span-2 flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {submitting ? 'Saving...' : 'Save provider'}
            </button>
          </div>
        </form>
      ) : null}

      <div className="rounded-md border border-border-subtle bg-bg-elevated">
        <table className="w-full text-sm" aria-label="Data providers">
          <thead className="bg-bg-base text-left text-xs uppercase text-text-secondary">
            <tr>
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Kind</th>
              <th className="px-3 py-2">Category</th>
              <th className="px-3 py-2">Mode</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {providers === null ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-text-secondary">
                  Loading...
                </td>
              </tr>
            ) : providers.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-4 text-text-secondary">
                  No providers configured yet.
                </td>
              </tr>
            ) : (
              providers.map((p) => (
                <tr key={p.id} className="border-t border-border-subtle">
                  <td className="px-3 py-2 text-text-primary">{p.label}</td>
                  <td className="px-3 py-2">{p.kind}</td>
                  <td className="px-3 py-2">{p.category}</td>
                  <td className="px-3 py-2">{p.mode}</td>
                  <td className="px-3 py-2">
                    {p.is_enabled ? 'enabled' : 'disabled'}
                    {p.has_api_key ? ' · key set' : ''}
                  </td>
                  <td className="px-3 py-2 text-right space-x-2">
                    <button
                      type="button"
                      data-action="test"
                      onClick={() => onTest(p)}
                      className="text-xs text-accent-primary hover:underline"
                    >
                      Test
                    </button>
                    <button
                      type="button"
                      data-action="delete"
                      onClick={() => onDelete(p)}
                      className="text-xs text-feedback-error hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <section className="space-y-2">
        <h3 className="text-sm font-medium text-text-primary">Requirement mappings</h3>
        <p className="text-xs text-text-secondary">
          Pick the provider that fulfills each requirement type. Empty rows mean no provider is assigned.
        </p>
        {mappings.length === 0 ? (
          <p className="text-xs text-text-secondary">No mappings configured yet.</p>
        ) : (
          <table className="w-full text-sm" aria-label="Requirement mappings">
            <thead className="text-left text-xs uppercase text-text-secondary">
              <tr>
                <th className="px-3 py-2">Requirement</th>
                <th className="px-3 py-2">Provider</th>
                <th className="px-3 py-2">Priority</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((row) => (
                <tr
                  key={`${row.requirement_type}-${row.provider_id}`}
                  className="border-t border-border-subtle"
                >
                  <td className="px-3 py-2 text-text-primary">{row.requirement_type}</td>
                  <td className="px-3 py-2">
                    <select
                      aria-label={`Provider for ${row.requirement_type}`}
                      defaultValue={row.provider_id}
                      onChange={(e) => onAssignMapping(row.requirement_type, e.target.value)}
                      className="rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                    >
                      {(providers ?? []).map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-3 py-2">{row.priority}</td>
                  <td className="px-3 py-2"></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  );
}
