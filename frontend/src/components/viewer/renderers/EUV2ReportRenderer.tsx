/**
 * Renderer for EU v2 earnings-update reports inside FileViewer.
 *
 * Fetches the EU v2 ``RunDetail``, adapts it to a v1 ``ReportSchema``
 * via ``adaptEuV2DetailToSchema``, and hands the result to the shared
 * ``ReportRenderer``. EU v2 reports then pick up the same branded
 * chrome as v1/v2.2/v2.3/v3 — ReportCover, TableOfContents,
 * BlockRenderer (with the native chart components, design tokens,
 * hover affordances), and the CitationsRail.
 *
 * Clone of V3ReportRenderer; only the fetch + adapter differ.
 */
import { useCallback, useEffect, useState, type JSX } from "react";

import { fetchCapabilities } from "../../../api/capabilities";
import { getRun, type RunDetail } from "../../../api/earnings-update";
import { adaptEuV2DetailToSchema } from "../../report/adapters/euV2DetailAdapter";
import { ReportRenderer } from "../../report/ReportRenderer";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

export function EUV2ReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const reportId = source.kind === "eu_v2_report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await getRun(reportId);
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
      <RendererError message="EU v2 report viewer requires a report id." onRetry={load} />
    );
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !detail) {
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;
  }

  const schema = adaptEuV2DetailToSchema(detail);
  return <ReportRenderer schema={schema} reportId={reportId} devMode={devMode} />;
}
