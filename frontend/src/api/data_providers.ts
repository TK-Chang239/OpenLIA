/**
 * Typed admin client for /settings/data-providers/*.
 */
import { request } from './_request';

export type ProviderCategory = 'financial' | 'news' | 'social_media' | 'search';
export type ProviderMode = 'api_key' | 'mcp';

export interface DataProvider {
  id: string;
  kind: string;
  label: string;
  category: ProviderCategory;
  mode: ProviderMode;
  base_url: string | null;
  mcp_url: string | null;
  env_var_name: string | null;
  has_api_key: boolean;
  is_enabled: boolean;
  extra_config: Record<string, unknown>;
}

export interface DataProviderCreate {
  kind: string;
  label: string;
  category: ProviderCategory;
  mode: ProviderMode;
  api_key?: string | null;
  env_var_name?: string | null;
  base_url?: string | null;
  mcp_url?: string | null;
  mcp_auth_header?: string | null;
  extra_config?: Record<string, unknown> | null;
}

export interface DataProviderUpdate {
  label?: string | null;
  api_key?: string | null;
  env_var_name?: string | null;
  base_url?: string | null;
  mcp_url?: string | null;
  mcp_auth_header?: string | null;
  extra_config?: Record<string, unknown> | null;
  is_enabled?: boolean | null;
}

export interface RequirementMapping {
  requirement_type: string;
  provider_id: string;
  priority: number;
}

export const listDataProviders = () =>
  request<{ providers: DataProvider[] }>('/api/settings/data-providers');

export const createDataProvider = (body: DataProviderCreate) =>
  request<DataProvider>('/api/settings/data-providers', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export const updateDataProvider = (id: string, body: DataProviderUpdate) =>
  request<DataProvider>(`/api/settings/data-providers/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });

export const deleteDataProvider = (id: string) =>
  request<void>(`/api/settings/data-providers/${id}`, { method: 'DELETE' });

export const testDataProviderConnection = (id: string) =>
  request<{ ok: boolean }>(`/api/settings/data-providers/${id}/test-connection`, {
    method: 'POST',
  });

export const listRequirementMappings = () =>
  request<{ mappings: RequirementMapping[] }>('/api/settings/data-providers/mappings');

export const setRequirementMapping = (
  requirementType: string,
  body: { provider_id: string; priority: number },
) =>
  request<RequirementMapping>(
    `/api/settings/data-providers/mappings/${requirementType}`,
    { method: 'PUT', body: JSON.stringify(body) },
  );

export const deleteRequirementMapping = (requirementType: string, providerId: string) =>
  request<void>(
    `/api/settings/data-providers/mappings/${requirementType}/${providerId}`,
    { method: 'DELETE' },
  );
