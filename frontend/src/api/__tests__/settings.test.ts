import { describe, expect, it, beforeEach, vi } from 'vitest';
import { getPrefs, updatePrefs, updateEmail, getModelPreferences, putModelPreference, deleteModelPreference } from '../settings';

describe('settings api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('GET /settings/prefs returns typed payload', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        display_name: 'Alice',
        theme: 'system',
        notify_inapp: true,
        notify_email: false,
        display_language: 'en',
        response_language: 'en',
        report_language: 'en',
      }),
    });
    const prefs = await getPrefs();
    expect(prefs.theme).toBe('system');
    expect(prefs.display_name).toBe('Alice');
  });

  it('PATCH /settings/prefs posts JSON patch body', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ display_name: 'Bob', theme: 'dark', notify_inapp: true, notify_email: false, display_language: 'en', response_language: 'en', report_language: 'en' }) });
    await updatePrefs({ theme: 'dark', display_name: 'Bob' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/prefs');
    expect(init.method).toBe('PATCH');
    expect(JSON.parse(init.body)).toEqual({ theme: 'dark', display_name: 'Bob' });
  });

  it('PATCH /settings/email surfaces 409 email_in_use', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: { code: 'email_in_use', message: 'x' } }),
    });
    await expect(updateEmail({ new_email: 'a@b.co', current_password: 'x' })).rejects.toMatchObject({
      code: 'email_in_use',
    });
  });

  it('GET /settings/admin/llm/preferences returns list', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ items: [{ tier: 'thinking', provider_id: 'openai', model_id: 'gpt-4o' }] }),
    });
    const prefs = await getModelPreferences();
    expect(prefs.items[0].tier).toBe('thinking');
  });

  it('PUT /settings/admin/llm/preferences/{tier}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await putModelPreference('quick', { provider_id: 'openai', model_id: 'gpt-4o-mini' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/admin/llm/preferences/quick');
    expect(init.method).toBe('PUT');
  });

  it('DELETE /settings/admin/llm/preferences/{tier}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await deleteModelPreference('quick');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/admin/llm/preferences/quick');
    expect(init.method).toBe('DELETE');
  });
});
