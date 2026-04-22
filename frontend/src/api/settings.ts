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
}

export interface PrefsPatch {
  display_name?: string;
  theme?: Theme;
  notify_inapp?: boolean;
  notify_email?: boolean;
  display_language?: LangCode;
  response_language?: LangCode;
  report_language?: LangCode;
}

export interface EmailUpdateIn {
  new_email: string;
  current_password: string;
}

export interface ModelPreferences {
  preferences: Record<Tier, string>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    const detail = body.detail ?? {};
    throw new ApiError(r.status, detail.code ?? 'http_error', detail.message ?? `HTTP ${r.status}`);
  }
  return r.json();
}

export const getPrefs = () => request<Prefs>('/api/settings/prefs');

export const updatePrefs = (patch: PrefsPatch) =>
  request<Prefs>('/api/settings/prefs', { method: 'PATCH', body: JSON.stringify(patch) });

export const updateEmail = (body: EmailUpdateIn) =>
  request<{ email: string }>('/api/settings/email', { method: 'PATCH', body: JSON.stringify(body) });

export const getModelPreferences = () =>
  request<ModelPreferences>('/api/settings/admin/llm/preferences');

export const putModelPreference = (tier: Tier, model_id: string) =>
  request<{ ok: true }>('/api/settings/admin/llm/preferences', {
    method: 'PUT',
    body: JSON.stringify({ tier, model_id }),
  });

export const deleteModelPreference = (tier: Tier) =>
  request<{ ok: true }>(`/api/settings/admin/llm/preferences/${tier}`, { method: 'DELETE' });
