export type Theme = 'system' | 'light' | 'dark';
export type LangCode = 'en' | 'zh-TW' | 'both';
export type TimezoneSource = 'auto' | 'manual';

export interface Prefs {
  display_name: string;
  theme: Theme;
  notify_inapp: boolean;
  notify_email: boolean;
  display_language: LangCode;
  response_language: LangCode;
  report_language: LangCode;
  preferred_model_id?: string | null;
  timezone: string;
  timezone_source: TimezoneSource;
  graph_extraction_time: string;
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

export interface TimezoneIn {
  timezone: string;
  source: TimezoneSource;
}

export interface GraphExtractionTimeIn {
  time: string;
}

export interface EmailUpdateIn {
  new_email: string;
  current_password: string;
}

export interface RosterEntry {
  id: string;
  model_ref: string;
  display_name: string;
  provider_id: string;
  provider_kind: string;
  is_enabled: boolean;
}

export interface EffectiveModel {
  model_ref: string;
  provider_kind: string;
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

// Path is "/enabled-models", not "/models": the bare "/settings/models" path
// collides with the SPA page route of the same name (see settings_general.py).
export const getEnabledModels = () =>
  request<RosterEntry[]>('/api/settings/enabled-models');

export const getEffectiveModel = (departmentId: string) =>
  request<EffectiveModel>(`/api/settings/models/effective/${departmentId}`);

export const getRegisteredDepartmentIds = () =>
  request<{ departments: string[] }>('/api/settings/departments').then((r) => r.departments);

export const updateTimezone = (body: TimezoneIn) =>
  request<Prefs>('/api/settings/timezone', {
    method: 'PUT',
    body: JSON.stringify(body),
  });

export const updateGraphExtractionTime = (body: GraphExtractionTimeIn) =>
  request<Prefs>('/api/settings/graph-extraction-time', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
