import { describe, expect, it, vi } from 'vitest';
import { listSkills, toggleSkill } from '../skills';

describe('skills api', () => {
  it('listSkills hits GET /api/skills', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ items: [] }), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    await listSkills();
    expect(fetch).toHaveBeenCalledWith('/api/skills', expect.any(Object));
  });

  it('toggleSkill PATCHes with enabled flag', async () => {
    const fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({}), { status: 200 }),
    );
    vi.stubGlobal('fetch', fetch);
    await toggleSkill('alpha', false);
    const call = fetch.mock.calls[0];
    expect(call[0]).toBe('/api/skills/alpha');
    expect(call[1].method).toBe('PATCH');
    expect(JSON.parse(call[1].body)).toEqual({ enabled: false });
  });
});
