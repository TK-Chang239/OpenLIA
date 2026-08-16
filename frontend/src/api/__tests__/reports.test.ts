import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  fetchReport,
  reportPdfUrl,
  downloadReportBlob,
  DownloadError,
} from '../reports';

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

describe('downloadReportBlob — expired (410) export', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('surfaces the structured detail.message from a tombstone 410 body', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 410,
      json: async () => ({
        detail: {
          code: 'report_expired',
          message: 'This report has expired and is no longer available.',
        },
      }),
    } as Response);

    const err = await downloadReportBlob('abc', 'pdf').catch((e) => e);
    expect(err).toBeInstanceOf(DownloadError);
    expect((err as DownloadError).status).toBe(410);
    expect((err as DownloadError).message).toBe(
      'This report has expired and is no longer available.',
    );
  });

  it('still surfaces a plain string detail body', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({ detail: 'Forbidden' }),
    } as Response);

    const err = await downloadReportBlob('abc', 'pdf').catch((e) => e);
    expect((err as DownloadError).message).toBe('Forbidden');
  });
});
