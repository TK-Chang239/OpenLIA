import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchReport, reportPdfUrl } from '../reports';

describe('fetchReport', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('calls /api/reports/{id} and returns the parsed schema', async () => {
    const spy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        schema: {
          schema_version: '1.0',
          department: 'equity_research',
          cover: { title: 'Apple Inc.', subtitle: 'Q1', tagline: 't', ticker: 'AAPL' },
          sections: [],
        },
      }),
    } as Response);
    const schema = await fetchReport('abc');
    expect(spy).toHaveBeenCalledWith('/api/reports/abc', { credentials: 'include' });
    expect(schema.cover.ticker).toBe('AAPL');
  });

  it('throws on non-2xx responses', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'not found',
    } as Response);
    await expect(fetchReport('abc')).rejects.toThrow(/404/);
  });
});

describe('reportPdfUrl', () => {
  it('returns the PDF export route', () => {
    expect(reportPdfUrl('abc')).toBe('/api/reports/abc/export/pdf');
  });
});
