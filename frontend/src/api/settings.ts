export type Theme = 'system' | 'light' | 'dark';
export type LangCode = 'en' | 'zh-TW' | 'both';
export type Tier = 'everyday' | 'quick' | 'thinking';

export interface Prefs {
  display_name: string;
  theme: Theme;
  notify_inapp: boolean;
  notify_email: boolean;
  display_language: LangCode;
  response_language: LangCode;
  report_language: LangCode;
  preferred_model_id?: string | null;
}

export interface PrefsPatch {
  display_name?: string;
  theme?: Theme;
  notify_inapp?: boolean;
  notify_email?: boolean;
  display_language?: LangCode;
  response_language?: LangCode;
  report_language?: LangCode;
  preferred_model_id?: string | null;
}

export interface EmailUpdateIn {
  new_email: string;
  current_password: string;
}

export interface ModelPreferences {
  preferences: Record<string, string>;
}

export interface RosterEntry {
  id: string;
  model_ref: string;
  display_name: string;
  provider_id: string;
  provider_kind: string;
  is_tier_default: boolean;
  is_enabled: boolean;
}

export interface ModelsRoster {
  thinking: RosterEntry[];
  everyday: RosterEntry[];
  quick: RosterEntry[];
}

export interface EffectiveModel {
  model_ref: string;
  provider_kind: string;
  tier: string;
  model_id: string;
  provider_id: string;
}

export { ApiError } from './_request';
import { request } from './_request';

export const getPrefs = () => request<Prefs>('/api/settings/prefs');

export const updatePrefs = (patch: PrefsPatch) =>
  request<Prefs>('/api/settings/prefs', { method: 'PATCH', body: JSON.stringify(patch) });

export const updateEmail = (body: EmailUpdateIn) =>
  request<{ email: string }>('/api/settings/email', { method: 'PATCH', body: JSON.stringify(body) });

export const getModelsRoster = () => request<ModelsRoster>('/api/settings/models');

export const getModelPreferences = () =>
  request<ModelPreferences>('/api/settings/models/preferences');

export const putModelPreference = (tier: Tier, model_id: string) =>
  request<{ ok: true }>(`/api/settings/models/preferences/${tier}`, {
    method: 'PUT',
    body: JSON.stringify({ model_id }),
  });

export const deleteModelPreference = (tier: Tier) =>
  request<{ ok: true }>(`/api/settings/models/preferences/${tier}`, { method: 'DELETE' });

export const getEffectiveModel = (departmentId: string) =>
  request<EffectiveModel>(`/api/settings/models/effective/${departmentId}`);

export interface DepartmentDefaultRow {
  department_id: string;
  tier: string;
  reason: string;
}

export interface DepartmentDefaults {
  departments: DepartmentDefaultRow[];
}

export const getDepartmentDefaults = () =>
  request<DepartmentDefaults>('/api/settings/models/department-defaults');
