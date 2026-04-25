/**
 * Server-wide LLM provider + model administration panel.
 *
 * Surface (per Phase 11 spec):
 *   - Provider cards with inline create/update/delete + connection test
 *   - Per-provider model table with inline create/update/delete
 *   - Tier-default toggle (server enforces "at most one default per tier")
 *   - Banner when any tier has zero enabled models
 */
import { FormEvent, useEffect, useMemo, useState } from 'react';
import { ApiError } from '../../../api/_request';
import {
  AdminConnectionTest,
  AdminModel,
  AdminProvider,
  AdminProviderCreate,
  AdminProviderUpdate,
  ProviderKind,
  Tier,
  createAdminModel,
  createAdminProvider,
  deleteAdminModel,
  deleteAdminProvider,
  listAdminModelsForProvider,
  listAdminProviders,
  testAdminProviderConfig,
  updateAdminModel,
  updateAdminProvider,
} from '../../../api/llm_admin';
import { InlineFeedback } from '../InlineFeedback';

const TIERS: Tier[] = ['thinking', 'everyday', 'quick'];
const PROVIDER_KINDS: ProviderKind[] = [
  'openai',
  'anthropic',
  'gemini',
  'openrouter',
  'openai_compat',
  'ollama',
];

interface ProviderFormState {
  kind: ProviderKind;
  label: string;
  api_key: string;
  base_url: string;
  env_var_name: string;
  test_model: string;
}

const EMPTY_FORM: ProviderFormState = {
  kind: 'openai',
  label: '',
  api_key: '',
  base_url: '',
  env_var_name: '',
  test_model: '',
};

interface ModelFormState {
  tier: Tier;
  model_ref: string;
  display_name: string;
  is_tier_default: boolean;
  is_enabled: boolean;
}

const EMPTY_MODEL_FORM: ModelFormState = {
  tier: 'everyday',
  model_ref: '',
  display_name: '',
  is_tier_default: false,
  is_enabled: true,
};

function tiersWithoutEnabledModel(grouped: Record<string, AdminModel[]>): Tier[] {
  const flat: AdminModel[] = Object.values(grouped).flat();
  return TIERS.filter((t) => !flat.some((m) => m.tier === t && m.is_enabled));
}

export function ModelsAdminPanel(): JSX.Element {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, AdminModel[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [providerForm, setProviderForm] = useState<ProviderFormState>(EMPTY_FORM);
  const [providerSubmitting, setProviderSubmitting] = useState(false);
  const [providerTestResult, setProviderTestResult] = useState<AdminConnectionTest | null>(null);
  const [modelFormByProvider, setModelFormByProvider] = useState<Record<string, ModelFormState>>(
    {},
  );

  const refresh = async () => {
    try {
      const provs = await listAdminProviders();
      const grouped: Record<string, AdminModel[]> = {};
      for (const p of provs) {
        grouped[p.id] = await listAdminModelsForProvider(p.id);
      }
      setProviders(provs);
      setModelsByProvider(grouped);
      setError(null);
    } catch (e) {
      setError((e as ApiError).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const tiersMissingModels = useMemo(
    () => tiersWithoutEnabledModel(modelsByProvider),
    [modelsByProvider],
  );

  const onTestProvider = async () => {
    setProviderTestResult(null);
    try {
      const result = await testAdminProviderConfig({
        kind: providerForm.kind,
        api_key: providerForm.api_key || null,
        base_url: providerForm.base_url || null,
        env_var_name: providerForm.env_var_name || null,
        model: providerForm.test_model,
      });
      setProviderTestResult(result);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const onCreateProvider = async (e: FormEvent) => {
    e.preventDefault();
    setProviderSubmitting(true);
    try {
      const body: AdminProviderCreate = {
        kind: providerForm.kind,
        label: providerForm.label.trim(),
        api_key: providerForm.api_key || null,
        base_url: providerForm.base_url || null,
        env_var_name: providerForm.env_var_name || null,
        run_test: !!providerForm.test_model,
        skip_reason: providerForm.test_model ? null : 'manual entry without test model',
        test_model: providerForm.test_model || null,
      };
      await createAdminProvider(body);
      setProviderForm(EMPTY_FORM);
      setProviderTestResult(null);
      setShowAddProvider(false);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    } finally {
      setProviderSubmitting(false);
    }
  };

  const onDeleteProvider = async (p: AdminProvider) => {
    if (!confirm(`Delete provider ${p.label}? Models attached must be removed first.`)) return;
    try {
      await deleteAdminProvider(p.id);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onToggleProvider = async (p: AdminProvider) => {
    try {
      const update: AdminProviderUpdate = { is_enabled: !p.is_enabled };
      await updateAdminProvider(p.id, update);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onCreateModel = async (providerId: string, e: FormEvent) => {
    e.preventDefault();
    const form = modelFormByProvider[providerId] ?? EMPTY_MODEL_FORM;
    try {
      await createAdminModel({
        provider_id: providerId,
        tier: form.tier,
        model_ref: form.model_ref.trim(),
        display_name: form.display_name.trim(),
        is_tier_default: form.is_tier_default,
        is_enabled: form.is_enabled,
        overrides: null,
      });
      setModelFormByProvider((prev) => ({ ...prev, [providerId]: EMPTY_MODEL_FORM }));
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onSetTierDefault = async (m: AdminModel) => {
    try {
      await updateAdminModel(m.id, {
        provider_id: m.provider_id,
        tier: m.tier,
        model_ref: m.model_ref,
        display_name: m.display_name,
        is_tier_default: true,
        is_enabled: m.is_enabled,
        overrides: m.overrides ?? null,
      });
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onToggleModelEnabled = async (m: AdminModel) => {
    try {
      await updateAdminModel(m.id, {
        provider_id: m.provider_id,
        tier: m.tier,
        model_ref: m.model_ref,
        display_name: m.display_name,
        is_tier_default: m.is_tier_default,
        is_enabled: !m.is_enabled,
        overrides: m.overrides ?? null,
      });
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onDeleteModel = async (m: AdminModel) => {
    if (!confirm(`Delete model ${m.display_name}?`)) return;
    try {
      await deleteAdminModel(m.id);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-base font-semibold text-text-primary">Server-wide models</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Register, test, or remove models for each capability tier. These become the defaults for all users.
        </p>
      </header>

      {error ? <InlineFeedback kind="error" message={error} /> : null}

      {tiersMissingModels.map((tier) => (
        <div
          key={tier}
          role="status"
          className="rounded-md border border-feedback-warning/30 bg-feedback-warning/10 px-3 py-2 text-sm text-feedback-warning"
        >
          The {tier} tier has no models configured. Add or enable a model so requests can resolve.
        </div>
      ))}

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-text-primary">Providers</h3>
          <button
            type="button"
            onClick={() => setShowAddProvider((v) => !v)}
            className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover"
          >
            {showAddProvider ? 'Cancel' : 'Add provider'}
          </button>
        </div>

        {showAddProvider ? (
          <form
            onSubmit={onCreateProvider}
            className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3"
            aria-label="Add provider"
          >
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-text-secondary">
                Kind
                <select
                  value={providerForm.kind}
                  onChange={(e) =>
                    setProviderForm((s) => ({ ...s, kind: e.target.value as ProviderKind }))
                  }
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                >
                  {PROVIDER_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-xs text-text-secondary">
                Label
                <input
                  type="text"
                  required
                  value={providerForm.label}
                  onChange={(e) => setProviderForm((s) => ({ ...s, label: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <label className="text-xs text-text-secondary">
                API key
                <input
                  type="password"
                  value={providerForm.api_key}
                  onChange={(e) => setProviderForm((s) => ({ ...s, api_key: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <label className="text-xs text-text-secondary">
                Env var name (alt)
                <input
                  type="text"
                  value={providerForm.env_var_name}
                  onChange={(e) =>
                    setProviderForm((s) => ({ ...s, env_var_name: e.target.value }))
                  }
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <label className="text-xs text-text-secondary">
                Base URL (optional)
                <input
                  type="text"
                  value={providerForm.base_url}
                  onChange={(e) => setProviderForm((s) => ({ ...s, base_url: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <label className="text-xs text-text-secondary">
                Test model (optional)
                <input
                  type="text"
                  value={providerForm.test_model}
                  onChange={(e) => setProviderForm((s) => ({ ...s, test_model: e.target.value }))}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onTestProvider}
                disabled={!providerForm.test_model}
                className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover disabled:opacity-50"
              >
                Test connection
              </button>
              {providerTestResult ? (
                <span
                  className={`text-xs ${
                    providerTestResult.ok ? 'text-feedback-success' : 'text-feedback-error'
                  }`}
                >
                  {providerTestResult.ok
                    ? `OK (${providerTestResult.latency_ms} ms)`
                    : `Failed: ${providerTestResult.error_msg ?? 'unknown'}`}
                </span>
              ) : null}
            </div>
            <button
              type="submit"
              disabled={providerSubmitting}
              className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
            >
              {providerSubmitting ? 'Saving...' : 'Save provider'}
            </button>
          </form>
        ) : null}
      </section>

      {providers.length === 0 ? (
        <p className="text-sm text-text-secondary">
          No providers configured. Click "Add provider" to register one.
        </p>
      ) : null}

      {providers.map((p) => {
        const models = modelsByProvider[p.id] ?? [];
        const modelForm = modelFormByProvider[p.id] ?? EMPTY_MODEL_FORM;
        return (
          <section
            key={p.id}
            className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
          >
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-medium text-text-primary">
                  {p.label} <span className="text-text-secondary">({p.kind})</span>
                </h3>
                <p className="text-xs text-text-secondary">
                  {p.is_enabled ? 'enabled' : 'disabled'} ·{' '}
                  {p.has_api_key ? 'credential set' : 'no credential'}
                </p>
              </div>
              <div className="flex gap-2 text-xs">
                <button
                  type="button"
                  onClick={() => onToggleProvider(p)}
                  className="text-accent-primary hover:underline"
                >
                  {p.is_enabled ? 'Disable' : 'Enable'}
                </button>
                <button
                  type="button"
                  onClick={() => onDeleteProvider(p)}
                  className="text-feedback-error hover:underline"
                >
                  Delete
                </button>
              </div>
            </div>

            {models.length === 0 ? (
              <p className="text-xs text-text-secondary">No models for this provider.</p>
            ) : (
              <table className="w-full text-xs" aria-label={`Models for ${p.label}`}>
                <thead className="text-text-secondary">
                  <tr>
                    <th className="text-left">Model</th>
                    <th className="text-left">Tier</th>
                    <th className="text-left">Default</th>
                    <th className="text-left">Enabled</th>
                    <th className="text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={m.id} className="border-t border-border-subtle">
                      <td>
                        {m.display_name}{' '}
                        <span className="text-text-secondary">({m.model_ref})</span>
                      </td>
                      <td>{m.tier}</td>
                      <td>{m.is_tier_default ? 'yes' : ''}</td>
                      <td>{m.is_enabled ? 'yes' : 'no'}</td>
                      <td className="text-right space-x-2">
                        {!m.is_tier_default ? (
                          <button
                            type="button"
                            onClick={() => onSetTierDefault(m)}
                            className="text-accent-primary hover:underline"
                          >
                            Set default
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => onToggleModelEnabled(m)}
                          className="text-text-primary hover:underline"
                        >
                          {m.is_enabled ? 'Disable' : 'Enable'}
                        </button>
                        <button
                          type="button"
                          onClick={() => onDeleteModel(m)}
                          className="text-feedback-error hover:underline"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <form
              onSubmit={(e) => onCreateModel(p.id, e)}
              className="grid grid-cols-5 gap-2 text-xs"
              aria-label={`Add model to ${p.label}`}
            >
              <input
                type="text"
                placeholder="model_ref"
                required
                value={modelForm.model_ref}
                onChange={(e) =>
                  setModelFormByProvider((prev) => ({
                    ...prev,
                    [p.id]: { ...modelForm, model_ref: e.target.value },
                  }))
                }
                className="col-span-2 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
              <input
                type="text"
                placeholder="display name"
                required
                value={modelForm.display_name}
                onChange={(e) =>
                  setModelFormByProvider((prev) => ({
                    ...prev,
                    [p.id]: { ...modelForm, display_name: e.target.value },
                  }))
                }
                className="rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
              <select
                aria-label="tier"
                value={modelForm.tier}
                onChange={(e) =>
                  setModelFormByProvider((prev) => ({
                    ...prev,
                    [p.id]: { ...modelForm, tier: e.target.value as Tier },
                  }))
                }
                className="rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              >
                {TIERS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover"
              >
                Add model
              </button>
            </form>
          </section>
        );
      })}
    </div>
  );
}
