import { useEffect, useState, useCallback } from "react";
import {
  fetchReportDetail,
  isReportExpired,
  type ReportSchema,
} from "../../../api/reports";
import { fetchCapabilities } from "../../../api/capabilities";
import { ReportRenderer } from "../../report/ReportRenderer";
import { ReportTombstoneCard } from "../../report/ReportTombstoneCard";
import { RendererError, RendererLoading } from "./RendererStates";
import { type FileSource } from "../FileViewerContext";
import { V3ReportRenderer } from "./V3ReportRenderer";
import { EUV2ReportRenderer } from "./EUV2ReportRenderer";
import { MBReportRenderer } from "./MBReportRenderer";

type Status = "loading" | "ok" | "expired" | "error";

/**
 * Dispatcher for "report"-kind FileViewer entries. v1 reports (e.g.
 * Morning Briefing) load a structured schema and render with v1's
 * ReportRenderer; v3 and Earnings-Update v2 each have a dedicated
 * renderer. FileViewer chrome (header, tabs, close) is shared.
 */
export function StructuredReportRenderer({
  source,
}: {
  source: FileSource;
}): JSX.Element {
  if (source.kind === "v3_report") {
    return <V3ReportRenderer source={source} />;
  }
  if (source.kind === "eu_v2_report") {
    return <EUV2ReportRenderer source={source} />;
  }
  if (source.kind === "mb_report") {
    return <MBReportRenderer source={source} />;
  }
  return <V1SchemaReportRenderer source={source} />;
}

function V1SchemaReportRenderer({
  source,
}: {
  source: FileSource;
}): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [expiredAt, setExpiredAt] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const reportId = source.kind === "report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const detail = await fetchReportDetail(reportId);
      // Tombstoned rows come back with the schema blanked and expired_at
      // stamped. Render the designed "no longer available" card instead of
      // the raw RendererError (the old fetchReport() throw path).
      if (isReportExpired(detail) || detail.schema === null) {
        setExpiredAt(detail.expired_at);
        setStatus("expired");
        return;
      }
      setSchema(detail.schema);
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
    return (
      <RendererError
        message="Report viewer requires a report source."
        onRetry={load}
      />
    );
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "expired")
    return <ReportTombstoneCard expiredAt={expiredAt} />;
  if (status === "error" || !schema)
    return (
      <RendererError
        message={error ?? "Failed to load report."}
        onRetry={load}
      />
    );

  return (
    <ReportRenderer schema={schema} reportId={reportId} devMode={devMode} />
  );
}
