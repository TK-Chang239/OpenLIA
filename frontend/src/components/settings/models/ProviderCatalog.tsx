/**
 * Server-wide provider + model catalog with department slot-default chips.
 *
 * Replaces the old admin/ModelsAdminPanel. Admins see inline CRUD for
 * providers and models plus a row of DepartmentChips for each model that
 * toggles which departments default to that model. Non-admins see the
 * same table read-only (no Add/Edit/Delete, chips disabled).
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
import {
  deleteSlotDefault,
  listSlotDefaults,
  setSlotDefault,
  SlotDefault,
} from '../../../api/llm_slots';
import { InlineFeedback } from '../InlineFeedback';
import { DepartmentChips } from './DepartmentChips';

const PROVIDER_KINDS: ProviderKind[] = [
  'openai',
  'anthropic',
  'gemini',
  'openrouter',
  'openai_compat',
  'ollama',
];

interface Props {
  departments: string[];
  isAdmin: boolean;
}

interface ProviderFormState {
  kind: ProviderKind;
  label: string;
  api_key: string;
  base_url: string;
  env_var_name: string;
  test_model: string;
}

const EMPTY_PROVIDER_FORM: ProviderFormState = {
  kind: 'openai',
  label: '',
  api_key: '',
  base_url: '',
  env_var_name: '',
  test_model: '',
};

interface ModelFormState {
  model_ref: string;
  display_name: string;
  is_enabled: boolean;
}

const EMPTY_MODEL_FORM: ModelFormState = {
  model_ref: '',
  display_name: '',
  is_enabled: true,
};

export function ProviderCatalog({ departments, isAdmin }: Props): JSX.Element {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [modelsByProvider, setModelsByProvider] = useState<
    Record<string, AdminModel[]>
  >({});
  const [slotDefaults, setSlotDefaults] = useState<SlotDefault[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddProvider, setShowAddProvider] = useState(false);
  const [providerForm, setProviderForm] =
    useState<ProviderFormState>(EMPTY_PROVIDER_FORM);
  const [providerSubmitting, setProviderSubmitting] = useState(false);
  const [providerTestResult, setProviderTestResult] =
    useState<AdminConnectionTest | null>(null);
  const [modelFormByProvider, setModelFormByProvider] = useState<
    Record<string, ModelFormState>
  >({});
  // Inline edit-in-place state: one provider and one model may be under edit.
  const [editingProviderId, setEditingProviderId] = useState<string | null>(
    null,
  );
  const [providerEditForm, setProviderEditForm] = useState<{
    label: string;
    api_key: string;
    clear_api_key: boolean;
    base_url: string;
    env_var_name: string;
  }>({ label: '', api_key: '', clear_api_key: false, base_url: '', env_var_name: '' });
  const [editingModelId, setEditingModelId] = useState<string | null>(null);
  const [modelEditForm, setModelEditForm] = useState<{
    model_ref: string;
    display_name: string;
  }>({ model_ref: '', display_name: '' });

  const refresh = async () => {
    try {
      const provs = await listAdminProviders();
      const grouped: Record<string, AdminModel[]> = {};
      for (const p of provs) {
        grouped[p.id] = await listAdminModelsForProvider(p.id);
      }
      const slots = await listSlotDefaults();
      setProviders(provs);
      setModelsByProvider(grouped);
      setSlotDefaults(slots.defaults);
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

  const slotsByModelId = useMemo(() => {
    const out = new Map<string, Set<string>>();
    for (const sd of slotDefaults) {
      if (sd.slot_kind !== 'department') continue;
      const existing = out.get(sd.model_id) ?? new Set<string>();
      existing.add(sd.slot_id);
      out.set(sd.model_id, existing);
    }
    return out;
  }, [slotDefaults]);

  const toggleSlot = async (modelId: string, deptId: string) => {
    const current = slotsByModelId.get(modelId) ?? new Set<string>();
    try {
      if (current.has(deptId)) {
        await deleteSlotDefault('department', deptId);
      } else {
        await setSlotDefault('department', deptId, modelId);
      }
      const { defaults } = await listSlotDefaults();
      setSlotDefaults(defaults);
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

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
        skip_reason: providerForm.test_model
          ? null
          : 'manual entry without test model',
        test_model: providerForm.test_model || null,
      };
      await createAdminProvider(body);
      setProviderForm(EMPTY_PROVIDER_FORM);
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
    if (
      !confirm(
        `Delete provider ${p.label}? Models attached must be removed first.`,
      )
    )
      return;
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

  const startEditProvider = (p: AdminProvider) => {
    setEditingProviderId(p.id);
    setProviderEditForm({
      label: p.label,
      api_key: '',
      clear_api_key: false,
      base_url: p.base_url ?? '',
      env_var_name: p.env_var_name ?? '',
    });
  };

  const onSaveProvider = async (p: AdminProvider, e: FormEvent) => {
    e.preventDefault();
    try {
      // null/omitted => keep existing (server treats None as UNCHANGED); only
      // send api_key when the admin typed a new one, or clear it via the flag.
      const update: AdminProviderUpdate = {
        label: providerEditForm.label.trim() || null,
        base_url: providerEditForm.base_url.trim() || null,
        env_var_name: providerEditForm.env_var_name.trim() || null,
      };
      if (providerEditForm.clear_api_key) {
        update.clear_api_key = true;
      } else if (providerEditForm.api_key) {
        update.api_key = providerEditForm.api_key;
      }
      await updateAdminProvider(p.id, update);
      setEditingProviderId(null);
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
        model_ref: form.model_ref.trim(),
        display_name: form.display_name.trim(),
        is_enabled: form.is_enabled,
        overrides: null,
      });
      setModelFormByProvider((prev) => ({
        ...prev,
        [providerId]: EMPTY_MODEL_FORM,
      }));
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  const onToggleModelEnabled = async (m: AdminModel) => {
    try {
      await updateAdminModel(m.id, {
        provider_id: m.provider_id,
        model_ref: m.model_ref,
        display_name: m.display_name,
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

  const startEditModel = (m: AdminModel) => {
    setEditingModelId(m.id);
    setModelEditForm({ model_ref: m.model_ref, display_name: m.display_name });
  };

  const onSaveModel = async (m: AdminModel, e?: FormEvent) => {
    e?.preventDefault();
    try {
      await updateAdminModel(m.id, {
        provider_id: m.provider_id,
        model_ref: modelEditForm.model_ref.trim(),
        display_name: modelEditForm.display_name.trim(),
        is_enabled: m.is_enabled,
        overrides: m.overrides ?? null,
      });
      setEditingModelId(null);
      await refresh();
    } catch (err) {
      setError((err as ApiError).message);
    }
  };

  if (loading)
    return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="space-y-4">
      {error ? <InlineFeedback kind="error" message={error} /> : null}

      {isAdmin ? (
        <section className="space-y-2">
          <div className="flex items-center justify-end">
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
                      setProviderForm((s) => ({
                        ...s,
                        kind: e.target.value as ProviderKind,
                      }))
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
                    onChange={(e) =>
                      setProviderForm((s) => ({ ...s, label: e.target.value }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  API key
                  <input
                    type="password"
                    value={providerForm.api_key}
                    onChange={(e) =>
                      setProviderForm((s) => ({
                        ...s,
                        api_key: e.target.value,
                      }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  Env var name (alt)
                  <input
                    type="text"
                    value={providerForm.env_var_name}
                    onChange={(e) =>
                      setProviderForm((s) => ({
                        ...s,
                        env_var_name: e.target.value,
                      }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  Base URL (optional)
                  <input
                    type="text"
                    value={providerForm.base_url}
                    onChange={(e) =>
                      setProviderForm((s) => ({
                        ...s,
                        base_url: e.target.value,
                      }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  Test model (optional)
                  <input
                    type="text"
                    value={providerForm.test_model}
                    onChange={(e) =>
                      setProviderForm((s) => ({
                        ...s,
                        test_model: e.target.value,
                      }))
                    }
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
                      providerTestResult.ok
                        ? 'text-feedback-success'
                        : 'text-feedback-error'
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
      ) : null}

      {providers.length === 0 ? (
        <p className="text-sm text-text-secondary">
          {isAdmin
            ? 'No providers configured. Click "Add provider" to register one.'
            : 'No providers configured.'}
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
                  {p.label}{' '}
                  <span className="text-text-secondary">({p.kind})</span>
                </h3>
                <p className="text-xs text-text-secondary">
                  {p.is_enabled ? 'enabled' : 'disabled'} ·{' '}
                  {p.has_api_key ? 'credential set' : 'no credential'}
                </p>
              </div>
              {isAdmin ? (
                <div className="flex gap-2 text-xs">
                  <button
                    type="button"
                    onClick={() =>
                      editingProviderId === p.id
                        ? setEditingProviderId(null)
                        : startEditProvider(p)
                    }
                    className="text-accent-primary hover:underline"
                  >
                    {editingProviderId === p.id ? 'Cancel' : 'Edit'}
                  </button>
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
              ) : null}
            </div>

            {isAdmin && editingProviderId === p.id ? (
              <form
                onSubmit={(e) => onSaveProvider(p, e)}
                aria-label={`Edit provider ${p.label}`}
                className="grid grid-cols-2 gap-2 rounded-md border border-border-subtle bg-bg-base p-3"
              >
                <label className="text-xs text-text-secondary">
                  Label
                  <input
                    type="text"
                    value={providerEditForm.label}
                    onChange={(e) =>
                      setProviderEditForm((s) => ({ ...s, label: e.target.value }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  API key {p.has_api_key ? '(leave blank to keep)' : ''}
                  <input
                    type="password"
                    value={providerEditForm.api_key}
                    disabled={providerEditForm.clear_api_key}
                    onChange={(e) =>
                      setProviderEditForm((s) => ({ ...s, api_key: e.target.value }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm text-text-primary disabled:opacity-50"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  Base URL
                  <input
                    type="text"
                    value={providerEditForm.base_url}
                    onChange={(e) =>
                      setProviderEditForm((s) => ({ ...s, base_url: e.target.value }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                <label className="text-xs text-text-secondary">
                  Env var name
                  <input
                    type="text"
                    value={providerEditForm.env_var_name}
                    onChange={(e) =>
                      setProviderEditForm((s) => ({
                        ...s,
                        env_var_name: e.target.value,
                      }))
                    }
                    className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm text-text-primary"
                  />
                </label>
                {p.has_api_key ? (
                  <label className="col-span-2 flex items-center gap-2 text-xs text-text-secondary">
                    <input
                      type="checkbox"
                      checked={providerEditForm.clear_api_key}
                      onChange={(e) =>
                        setProviderEditForm((s) => ({
                          ...s,
                          clear_api_key: e.target.checked,
                        }))
                      }
                    />
                    Clear stored API key
                  </label>
                ) : null}
                <div className="col-span-2 flex justify-end gap-2">
                  <button
                    type="button"
                    onClick={() => setEditingProviderId(null)}
                    className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover"
                  >
                    Save provider
                  </button>
                </div>
              </form>
            ) : null}

            {models.length === 0 ? (
              <p className="text-xs text-text-secondary">
                No models for this provider.
              </p>
            ) : (
              <table
                className="w-full text-xs"
                aria-label={`Models for ${p.label}`}
              >
                <thead className="text-text-secondary">
                  <tr>
                    <th className="text-left">Model</th>
                    <th className="text-left">Departments</th>
                    <th className="text-left">Enabled</th>
                    {isAdmin ? <th className="text-right">Actions</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => {
                    const editing = isAdmin && editingModelId === m.id;
                    return (
                    <tr key={m.id} className="border-t border-border-subtle">
                      <td>
                        {editing ? (
                          <div className="flex gap-2">
                            <input
                              type="text"
                              aria-label="model_ref"
                              value={modelEditForm.model_ref}
                              onChange={(e) =>
                                setModelEditForm((s) => ({
                                  ...s,
                                  model_ref: e.target.value,
                                }))
                              }
                              className="w-1/2 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                            />
                            <input
                              type="text"
                              aria-label="display name"
                              value={modelEditForm.display_name}
                              onChange={(e) =>
                                setModelEditForm((s) => ({
                                  ...s,
                                  display_name: e.target.value,
                                }))
                              }
                              className="w-1/2 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                            />
                          </div>
                        ) : (
                          <>
                            {m.display_name}{' '}
                            <span className="text-text-secondary">
                              ({m.model_ref})
                            </span>
                          </>
                        )}
                      </td>
                      <td>
                        <DepartmentChips
                          departments={departments}
                          assigned={
                            slotsByModelId.get(m.id) ?? new Set<string>()
                          }
                          onToggle={(dept) => toggleSlot(m.id, dept)}
                          disabled={!isAdmin}
                        />
                      </td>
                      <td>{m.is_enabled ? 'yes' : 'no'}</td>
                      {isAdmin ? (
                        <td className="space-x-2 text-right">
                          {editing ? (
                            <>
                              <button
                                type="button"
                                onClick={() => onSaveModel(m)}
                                className="text-accent-primary hover:underline"
                              >
                                Save
                              </button>
                              <button
                                type="button"
                                onClick={() => setEditingModelId(null)}
                                className="text-text-primary hover:underline"
                              >
                                Cancel
                              </button>
                            </>
                          ) : (
                            <>
                              <button
                                type="button"
                                onClick={() => startEditModel(m)}
                                className="text-accent-primary hover:underline"
                              >
                                Edit
                              </button>
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
                            </>
                          )}
                        </td>
                      ) : null}
                    </tr>
                    );
                  })}
                </tbody>
              </table>
            )}

            {isAdmin ? (
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
                  className="col-span-2 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
                <button
                  type="submit"
                  className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover"
                >
                  Add model
                </button>
              </form>
            ) : null}
          </section>
        );
      })}
    </div>
  );
}
