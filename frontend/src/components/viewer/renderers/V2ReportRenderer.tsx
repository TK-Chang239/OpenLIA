/**
 * Renderer for v2.2 equity-research reports inside FileViewer.
 *
 * Fetches the structured ReportV2 JSON from
 * `/api/departments/equity-research/v2/runs/{runId}/report`, runs the
 * v2 → v1 block-type adapter, and hands the result to v1's
 * `ReportRenderer`. That puts v2 reports through the same branded
 * surface as v1 — ReportCover, TableOfContents, BlockRenderer (with
 * the project's design tokens, charts, hover affordances), and the
 * CitationsRail.
 *
 * Replaces the earlier iframe-based renderer entirely (Workstream B).
 */
import { useCallback, useEffect, useState, type JSX } from "react";

import { fetchCapabilities } from "../../../api/capabilities";
import { ReportRenderer } from "../../report/ReportRenderer";
import {
  adaptReportV2ToSchema,
  type ReportV2Wire,
} from "../../report/adapters/v2BlockAdapter";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

async function fetchV2Report(runId: string): Promise<ReportV2Wire> {
  const res = await fetch(
    `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}/report`,
    { credentials: "same-origin" },
  );
  if (!res.ok) {
    throw new Error(`fetchV2Report failed (${res.status} ${res.statusText ?? ""})`);
  }
  return res.json() as Promise<ReportV2Wire>;
}

export function V2ReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [report, setReport] = useState<ReportV2Wire | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [devMode, setDevMode] = useState(false);

  const runId = source.kind === "v2_report" ? source.runId : null;

  const load = useCallback(async () => {
    if (!runId) return;
    setStatus("loading");
    setError(null);
    try {
      const next = await fetchV2Report(runId);
      setReport(next);
      setStatus("ok");
    } catch (e) {
      setError((e as Error).message);
      setStatus("error");
    }
  }, [runId]);

  useEffect(() => {
    void load();
  }, [load]);

  // Same dev-mode gate the v1 path uses for the verification-history table.
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
    return <RendererError message="v2 report viewer requires a run id." onRetry={load} />;
  }
  if (status === "loading") return <RendererLoading />;
  if (status === "error" || !report)
    return <RendererError message={error ?? "Failed to load report."} onRetry={load} />;

  const schema = adaptReportV2ToSchema(report);
  return <ReportRenderer schema={schema} reportId={runId} devMode={devMode} />;
}
