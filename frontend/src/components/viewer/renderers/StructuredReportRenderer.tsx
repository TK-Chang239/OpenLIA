import { useEffect, useState, useCallback } from "react";
import { fetchReport, type ReportSchema } from "../../../api/reports";
import { fetchCapabilities } from "../../../api/capabilities";
import { ReportRenderer } from "../../report/ReportRenderer";
import { RendererError, RendererLoading } from "./RendererStates";
import { type FileSource } from "../FileViewerContext";
import { V2ReportRenderer } from "./V2ReportRenderer";

type Status = "loading" | "ok" | "error";

/**
 * Dispatcher for "report"-kind FileViewer entries. v1 reports load a
 * structured schema and render with v1's ReportRenderer; v2.2 reports
 * carry a single HTML payload and render through V2ReportRenderer.
 * FileViewer chrome (header, tabs, close) is shared in both cases.
 */
export function StructuredReportRenderer({ source }: { source: FileSource }): JSX.Element {
  if (source.kind === "v2_report") {
    return <V2ReportRenderer source={source} />;
  }
  return <V1SchemaReportRenderer source={source} />;
}

function V1SchemaReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const reportId = source.kind === "report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await fetchReport(reportId);
      setSchema(next);
      setStatus("ok");
    } catch (e) {
      setError((e as Error).message);
      setStatus("error");
    }
  }, [reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Look up the deployment's dev_mode flag once. Failure to fetch the
  // manifest (older deployments, network errors) just leaves dev_mode
  // off — the v2.2 backend would not be emitting verification history
  // payloads in that case anyway.
  useEffect(() => {
    let cancelled = false;
    void fetchCapabilities()
      .then((m) => {
        if (!cancelled) setDevMode(m.dev_mode);
      })
      .catch(() => {
        // Endpoint may be absent on pre-v2.2 deployments; stay quiet.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!reportId) {
    return <RendererError message="Report viewer requires a report source." onRetry={load} />;
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !schema)
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;

  return <ReportRenderer schema={schema} reportId={reportId} devMode={devMode} />;
}
