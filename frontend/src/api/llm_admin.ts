/**
 * Typed admin LLM CRUD client. Wraps `/settings/admin/llm/*`.
 */
import { request } from './_request';

export type ProviderKind =
  | 'openai'
  | 'anthropic'
  | 'gemini'
  | 'openrouter'
  | 'openai_compat'
  | 'ollama';

export interface AdminProvider {
  id: string;
  kind: ProviderKind;
  label: string;
  has_api_key: boolean;
  env_var_name: string | null;
  base_url: string | null;
  is_enabled: boolean;
  test?: AdminConnectionTest | null;
}

export interface AdminModel {
  id: string;
  provider_id: string;
  model_ref: string;
  display_name: string;
  is_enabled: boolean;
  overrides: Record<string, unknown> | null;
}

export interface AdminConnectionTest {
  ok: boolean;
  latency_ms: number;
  error_class: string | null;
  error_msg: string | null;
}

export interface AdminProviderCreate {
  kind: ProviderKind;
  label: string;
  api_key?: string | null;
  base_url?: string | null;
  env_var_name?: string | null;
  extra_config?: Record<string, unknown> | null;
  is_enabled?: boolean;
  run_test: boolean;
  skip_reason?: string | null;
  test_model?: string | null;
}

export interface AdminProviderUpdate {
  label?: string | null;
  api_key?: string | null;
  base_url?: string | null;
  env_var_name?: string | null;
  extra_config?: Record<string, unknown> | null;
  is_enabled?: boolean | null;
  clear_api_key?: boolean;
  clear_env_var_name?: boolean;
}

export interface AdminModelInput {
  provider_id: string;
  model_ref: string;
  display_name: string;
  is_enabled?: boolean;
  overrides?: Record<string, unknown> | null;
  advertised_capabilities?: Record<string, unknown> | null;
}

export const listAdminProviders = () =>
  request<AdminProvider[]>('/api/settings/admin/llm/providers');

export const createAdminProvider = (body: AdminProviderCreate) =>
  request<AdminProvider>('/api/settings/admin/llm/providers', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const updateAdminProvider = (id: string, body: AdminProviderUpdate) =>
  request<AdminProvider>(`/api/settings/admin/llm/providers/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });

export const deleteAdminProvider = (id: string) =>
  request<void>(`/api/settings/admin/llm/providers/${id}`, { method: 'DELETE' });

export const testAdminProviderConfig = (body: {
  kind: ProviderKind;
  api_key?: string | null;
  base_url?: string | null;
  env_var_name?: string | null;
  model: string;
}) =>
  request<AdminConnectionTest>('/api/settings/admin/llm/providers/test', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const listAdminModelsForProvider = (id: string) =>
  request<AdminModel[]>(`/api/settings/admin/llm/providers/${id}/models`);

export const createAdminModel = (body: AdminModelInput) =>
  request<AdminModel>('/api/settings/admin/llm/models', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const updateAdminModel = (id: string, body: AdminModelInput) =>
  request<AdminModel>(`/api/settings/admin/llm/models/${id}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  });

export const deleteAdminModel = (id: string) =>
  request<void>(`/api/settings/admin/llm/models/${id}`, { method: 'DELETE' });
