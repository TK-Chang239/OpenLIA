/**
 * Full-bleed, no-AppShell render of a v2.2 report. Mirrors v1's
 * ReportPrintPage but fetches the structured ReportV2 JSON and runs
 * the v2→v1 block adapter before handing it to ReportRenderer.
 *
 * Used by the backend's Playwright pipeline to PDF/DOCX-export v2 runs:
 * the v2 export route navigates to `/reports/v2/{runId}/render` and
 * waits for `window.__REPORT_READY__ === true` before printing /
 * screenshotting.
 */
import { useEffect, useState, type JSX } from "react";
import { useParams } from "react-router-dom";

import { ReportRenderer } from "../components/report/ReportRenderer";
import {
  adaptReportV2ToSchema,
  type ReportV2Wire,
} from "../components/report/adapters/v2BlockAdapter";
import type { ReportSchema } from "../api/reports";

declare global {
  interface Window {
    __REPORT_SCHEMA_V2__?: ReportV2Wire;
  }
}

async function fetchV2Report(runId: string): Promise<ReportV2Wire> {
  const res = await fetch(
    `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}/report`,
    { credentials: "include" },
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return (await res.json()) as ReportV2Wire;
}

export default function ReportPrintPageV2(): JSX.Element {
  const { runId } = useParams<{ runId: string }>();
  const injected =
    typeof window !== "undefined" ? window.__REPORT_SCHEMA_V2__ : undefined;
  const [schema, setSchema] = useState<ReportSchema | undefined>(
    injected ? adaptReportV2ToSchema(injected) : undefined,
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (schema || !runId) {
      if (schema && typeof window !== "undefined") {
        window.__REPORT_READY__ = true;
      }
      return;
    }
    let cancelled = false;
    fetchV2Report(runId)
      .then((rep) => {
        if (!cancelled) {
          setSchema(adaptReportV2ToSchema(rep));
          if (typeof window !== "undefined") {
            window.__REPORT_READY__ = true;
          }
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e));
          if (typeof window !== "undefined") {
            window.__REPORT_READY__ = true;
          }
        }
      });
    return () => {
      cancelled = true;
    };
  }, [runId, schema]);

  if (error) {
    return <div className="report-print-error">Failed to load report: {error}</div>;
  }

  return (
    <div className="report-print-root" data-report-print="1">
      <ReportRenderer schema={schema} loading={!schema} />
    </div>
  );
}
