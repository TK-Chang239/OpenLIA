import { useEffect, useState } from 'react';
import { ApiError } from '../../../api/settings';

interface AdminProvider {
  id: string;
  kind: string;
  label: string;
  has_api_key: boolean;
  env_var_name: string | null;
  base_url: string | null;
  is_enabled: boolean;
}

interface AdminModel {
  id: string;
  provider_id: string;
  tier: string;
  model_ref: string;
  display_name: string;
  is_tier_default: boolean;
  is_enabled: boolean;
  overrides: Record<string, unknown> | null;
}

async function adminRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = body.detail ?? {};
    throw new ApiError(r.status, detail.code ?? 'http_error', detail.error ?? detail.message ?? `HTTP ${r.status}`);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}

const listProviders = () => adminRequest<AdminProvider[]>('/api/settings/admin/llm/providers');
const listModelsForProvider = (id: string) =>
  adminRequest<AdminModel[]>(`/api/settings/admin/llm/providers/${id}/models`);
const deleteModel = (id: string) =>
  adminRequest<void>(`/api/settings/admin/llm/models/${id}`, { method: 'DELETE' });
const setTierDefault = (model: AdminModel) =>
  adminRequest<AdminModel>(`/api/settings/admin/llm/models/${model.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      provider_id: model.provider_id,
      tier: model.tier,
      model_ref: model.model_ref,
      display_name: model.display_name,
      is_tier_default: true,
      is_enabled: model.is_enabled,
      overrides: model.overrides ?? null,
    }),
  });

export function ModelsAdminPanel(): JSX.Element {
  const [providers, setProviders] = useState<AdminProvider[]>([]);
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, AdminModel[]>>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    try {
      const provs = await listProviders();
      const grouped: Record<string, AdminModel[]> = {};
      for (const p of provs) {
        grouped[p.id] = await listModelsForProvider(p.id);
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

  const onDelete = async (m: AdminModel) => {
    if (!confirm(`Delete model ${m.display_name}?`)) return;
    try {
      await deleteModel(m.id);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
    }
  };

  const onSetDefault = async (m: AdminModel) => {
    try {
      await setTierDefault(m);
      await refresh();
    } catch (e) {
      setError((e as ApiError).message);
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
      {error ? <p className="text-sm text-error">{error}</p> : null}
      {providers.length === 0 ? (
        <p className="text-sm text-text-secondary">No providers configured. Use the setup wizard or POST /settings/admin/llm/providers.</p>
      ) : null}
      {providers.map((p) => {
        const models = modelsByProvider[p.id] ?? [];
        return (
          <section key={p.id} className="space-y-2">
            <h3 className="text-sm font-medium text-text-primary">
              {p.label}{' '}
              <span className="opacity-70">({p.kind})</span>
              {p.is_enabled ? '' : ' — disabled'}
            </h3>
            {models.length === 0 ? (
              <p className="text-xs text-text-secondary">No models for this provider.</p>
            ) : (
              <table className="w-full text-xs">
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
                    <tr key={m.id}>
                      <td>{m.display_name} <span className="opacity-70">({m.model_ref})</span></td>
                      <td>{m.tier}</td>
                      <td>{m.is_tier_default ? 'yes' : ''}</td>
                      <td>{m.is_enabled ? 'yes' : 'no'}</td>
                      <td className="text-right space-x-2">
                        {!m.is_tier_default ? (
                          <button onClick={() => onSetDefault(m)} className="text-blue-600 hover:underline">
                            Set default
                          </button>
                        ) : null}
                        <button onClick={() => onDelete(m)} className="text-red-600 hover:underline">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        );
      })}
    </div>
  );
}
