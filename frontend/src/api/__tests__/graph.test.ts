import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  listProposals,
  acceptProposal,
  dismissProposal,
  listConstructs,
  deleteConstruct,
} from '../graph';

describe('graph api', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  it('GET /graph/proposals returns typed items', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        items: [
          {
            id: 'p1',
            kind: 'user_construct',
            payload: { statement: 'long NVDA', source_excerpt: 'I am long NVDA' },
            status: 'pending',
            created_at: '2026-05-09T00:00:00Z',
          },
        ],
      }),
    });
    const r = await listProposals();
    expect(r.items).toHaveLength(1);
    expect(r.items[0].kind).toBe('user_construct');
    const [url] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/proposals?status=pending');
  });

  it('POST /graph/proposals/{id}/accept', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => null });
    await acceptProposal('p1');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/proposals/p1/accept');
    expect(init.method).toBe('POST');
  });

  it('POST /graph/proposals/{id}/dismiss', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ ok: true }) });
    await dismissProposal('p1');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/proposals/p1/dismiss');
    expect(init.method).toBe('POST');
  });

  it('GET /graph/constructs no filter', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });
    await listConstructs();
    const [url] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/constructs');
  });

  it('GET /graph/constructs with entity_id', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });
    await listConstructs('ticker:NVDA');
    const [url] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/constructs?entity_id=ticker%3ANVDA');
  });

  it('DELETE /graph/constructs/{id}', async () => {
    (fetch as any).mockResolvedValueOnce({ ok: true, status: 204 });
    await deleteConstruct('c1');
    const [url, init] = (fetch as any).mock.calls[0];
    expect(url).toBe('/api/graph/constructs/c1');
    expect(init.method).toBe('DELETE');
  });

  it('surfaces ApiError detail.code on failure', async () => {
    (fetch as any).mockResolvedValueOnce({
      ok: false,
      status: 409,
      json: async () => ({ detail: { code: 'proposal_not_pending', message: 'resolved' } }),
    });
    await expect(acceptProposal('p1')).rejects.toMatchObject({ code: 'proposal_not_pending' });
  });
});
