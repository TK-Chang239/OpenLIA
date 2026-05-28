/**
 * Renderer for v3 equity-research reports inside FileViewer.
 *
 * Fetches the v3 ``ReportDetail``, adapts it to a v1 ``ReportSchema``
 * via ``adaptV3DetailToSchema``, and hands the result to the shared
 * ``ReportRenderer``. v3 reports then pick up the same branded
 * chrome as v1/v2.2/v2.3 — ReportCover, TableOfContents,
 * BlockRenderer (with the native chart components, design tokens,
 * hover affordances), and the CitationsRail.
 *
 * Mirrors V23ReportRenderer almost exactly; only the fetch + adapter
 * differ.
 */
import { useCallback, useEffect, useState, type JSX } from "react";

import { fetchCapabilities } from "../../../api/capabilities";
import { getV3Run, type V3ReportDetail } from "../../../api/equity-research-v3";
import { adaptV3DetailToSchema } from "../../report/adapters/v3DetailAdapter";
import { ReportRenderer } from "../../report/ReportRenderer";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

export function V3ReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const reportId = source.kind === "v3_report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await getV3Run(reportId);
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

  // Same dev-mode gate the v1/v2.2/v2.3 paths use.
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
      <RendererError message="v3 report viewer requires a report id." onRetry={load} />
    );
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !detail) {
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;
  }

  const schema = adaptV3DetailToSchema(detail);
  return <ReportRenderer schema={schema} reportId={reportId} devMode={devMode} />;
}
