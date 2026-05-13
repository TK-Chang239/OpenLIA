import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  getPrefs,
  updatePrefs,
  updateEmail,
  getEnabledModels,
  getRegisteredDepartmentIds,
  updateTimezone,
  updateGraphExtractionTime,
} from '../settings';

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

  it('GET /settings/models returns flat enabled models', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => [
        {
          id: 'm1',
          model_ref: 'gpt-4o',
          display_name: 'GPT-4o',
          provider_id: 'p1',
          provider_kind: 'openai',
          is_enabled: true,
        },
      ],
    });
    const models = await getEnabledModels();
    expect(models).toHaveLength(1);
    expect(models[0].model_ref).toBe('gpt-4o');
  });

  it('GET /settings/departments unwraps departments array', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ departments: ['secretary', 'equity_research'] }),
    });
    const deps = await getRegisteredDepartmentIds();
    expect(deps).toEqual(['secretary', 'equity_research']);
  });

  it('PUT /settings/timezone with timezone+source body', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await updateTimezone({ timezone: 'Asia/Taipei', source: 'manual' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/timezone');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({
      timezone: 'Asia/Taipei',
      source: 'manual',
    });
  });

  it('PUT /settings/graph-extraction-time with time body', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({}) });
    await updateGraphExtractionTime({ time: '04:30' });
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/settings/graph-extraction-time');
    expect(init.method).toBe('PUT');
    expect(JSON.parse(init.body)).toEqual({ time: '04:30' });
  });
});
