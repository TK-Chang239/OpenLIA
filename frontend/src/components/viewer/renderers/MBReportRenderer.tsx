/**
 * Renderer for Morning Briefing reports inside FileViewer.
 *
 * Fetches the MB ``RunDetail``, adapts it to a v1 ``ReportSchema`` via
 * ``adaptMbDetailToSchema``, and hands the result to the shared
 * ``ReportRenderer``. MB reports then pick up the same branded chrome as
 * v1/EU/v3 — ReportCover, TableOfContents, BlockRenderer (with native chart
 * components, design tokens, hover affordances), and the CitationsRail.
 *
 * Clone of EUV2ReportRenderer; only the fetch + adapter differ.
 */
import { useCallback, useEffect, useState, type JSX } from "react";

import { fetchCapabilities } from "../../../api/capabilities";
import { getMbRun, type MbRunDetail } from "../../../api/morning-briefing";
import { adaptMbDetailToSchema } from "../../report/adapters/mbDetailAdapter";
import { ReportRenderer } from "../../report/ReportRenderer";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

export function MBReportRenderer({
  source,
}: {
  source: FileSource;
}): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [detail, setDetail] = useState<MbRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const reportId = source.kind === "mb_report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await getMbRun(reportId);
      setDetail(next);
      setStatus("ok");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }, [reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    let cancelled = false;
    void fetchCapabilities()
      .then((m) => {
        if (!cancelled) setDevMode(m.dev_mode);
      })
      .catch(() => {
        /* manifest absent on older deployments; stay quiet. */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!reportId) {
    return (
      <RendererError
        message="Morning Briefing report viewer requires a report id."
        onRetry={load}
      />
    );
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !detail) {
    return (
      <RendererError
        message={error ?? "Failed to load report."}
        onRetry={load}
      />
    );
  }

  const schema = adaptMbDetailToSchema(detail);
  return (
    <ReportRenderer schema={schema} reportId={reportId} devMode={devMode} />
  );
}
