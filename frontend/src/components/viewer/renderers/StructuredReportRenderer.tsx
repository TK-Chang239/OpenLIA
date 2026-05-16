import { useEffect, useState, useCallback } from "react";
import { fetchReport, type ReportSchema } from "../../../api/reports";
import { ReportRenderer } from "../../report/ReportRenderer";
import { RendererError, RendererLoading } from "./RendererStates";
import { type FileSource } from "../FileViewerContext";

type Status = "loading" | "ok" | "error";

export function StructuredReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [schema, setSchema] = useState<ReportSchema | null>(null);
  const [error, setError] = useState<string | null>(null);

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

  if (!reportId) {
    return <RendererError message="Report viewer requires a report source." onRetry={load} />;
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !schema)
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;

  return <ReportRenderer schema={schema} reportId={reportId} />;
}
