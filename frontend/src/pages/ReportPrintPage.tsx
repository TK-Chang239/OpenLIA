import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';

import { fetchReport, type ReportSchema } from '../api/reports';
import { ReportRenderer } from '../components/report/ReportRenderer';

declare global {
  interface Window {
    __REPORT_SCHEMA__?: ReportSchema;
    __REPORT_READY__?: boolean;
  }
}

/**
 * Full-bleed, no-AppShell render of a report. Used for:
 * - Browser-driven print preview (`window.print()` or browser PDF export).
 * - Future Playwright-driven PDF rendering (Option A): the backend
 *   injects `window.__REPORT_SCHEMA__` before bundle load so this page
 *   mounts synchronously without a network round-trip.
 *
 * Schema sources, in priority order:
 *   1. `window.__REPORT_SCHEMA__` (server-injected, no auth needed).
 *   2. `GET /api/reports/:id` (browser session cookie path).
 */
export default function ReportPrintPage(): JSX.Element {
  const { id } = useParams<{ id: string }>();
  const injected = typeof window !== 'undefined' ? window.__REPORT_SCHEMA__ : undefined;
  const [schema, setSchema] = useState<ReportSchema | undefined>(injected);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (schema || !id) {
      // Inject path: signal readiness so headless drivers can wait on it.
      if (schema && typeof window !== 'undefined') {
        window.__REPORT_READY__ = true;
      }
      return;
    }
    let cancelled = false;
    fetchReport(id)
      .then((s) => {
        if (!cancelled) {
          setSchema(s);
          if (typeof window !== 'undefined') {
            window.__REPORT_READY__ = true;
          }
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [id, schema]);

  if (error) {
    return <div className="report-print-error">Failed to load report: {error}</div>;
  }

  return (
    <div className="report-print-root" data-report-print="1">
      <ReportRenderer schema={schema} loading={!schema} />
    </div>
  );
}
