/**
 * Renderer for v2.3 equity-research reports inside FileViewer.
 *
 * Fetches the v2.3 RunPayload, adapts it to a v1 ReportSchema, and
 * hands the result to the shared `ReportRenderer`. v2.3 reports then
 * pick up the same branded chrome as v2.2 + v1 — ReportCover,
 * TableOfContents, BlockRenderer (with native chart components and
 * design tokens), and the CitationsRail.
 *
 * Mirrors V2ReportRenderer almost exactly; only the fetch + adapter
 * differ.
 */
import { useCallback, useEffect, useState, type JSX } from "react";

import { getV23RunPayload, type V23RunPayload } from "../../../api/equity-research-v2-3";
import { fetchCapabilities } from "../../../api/capabilities";
import { adaptV23PayloadToSchema } from "../../report/adapters/v23PayloadAdapter";
import { ReportRenderer } from "../../report/ReportRenderer";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

export function V23ReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [payload, setPayload] = useState<V23RunPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const runId = source.kind === "v23_report" ? source.runId : null;

  const load = useCallback(async () => {
    if (!runId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await getV23RunPayload(runId);
      setPayload(next);
      setStatus("ok");
    } catch (e) {
      setError((e as Error).message);
      setStatus("error");
    }
  }, [runId]);

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

  if (!runId) {
    return <RendererError message="v2.3 report viewer requires a run id." onRetry={load} />;
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !payload)
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;

  const schema = adaptV23PayloadToSchema(payload);
  return <ReportRenderer schema={schema} reportId={runId} devMode={devMode} />;
}
