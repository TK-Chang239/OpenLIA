/**
 * V3ReportRenderer — in-browser React view of a v3 equity-research
 * report. Mounted inside the FileViewer side-window when the user
 * clicks "Open report" on a v3 ReportCard.
 *
 * Fetches the latest persisted state via ``getV3Run`` and renders:
 *   - Cover header (subject, template, status, meta counts)
 *   - Each section's markdown via react-markdown + remark-gfm
 *   - Chart placeholders (or the rendered PNG when available)
 *   - Bibliography (clickable URL when provenance carries one)
 *
 * The ``[^source_id]`` markers in section markdown get rewritten to
 * ``[^N]`` numeric footnotes on the fly using the citations'
 * ``display_index`` so the in-page view matches the standalone HTML.
 *
 * The ``/html`` and ``/pdf`` routes stay as the standalone-export
 * surface (new-tab open for Word/PDF saves); this component is the
 * "view inline" alternative.
 */
import { useCallback, useEffect, useState, type JSX } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import {
  type V3CitationRow,
  type V3ReportDetail,
  getV3Run,
} from "../../../api/equity-research-v3";
import { type FileSource } from "../FileViewerContext";
import { RendererError, RendererLoading } from "./RendererStates";

type Status = "loading" | "ok" | "error";

const CITATION_RE = /\[\^([a-z0-9_]+)\]/g;
const CHART_REF_RE = /\{\{chart:([a-z0-9_]+)\}\}/g;

function rewriteCitations(
  markdown: string,
  byId: Map<string, number>,
): string {
  return markdown.replace(CITATION_RE, (_match, sid) => {
    const n = byId.get(sid);
    return n ? `[^${n}]` : `[^${sid}]`;
  });
}

function buildDisplayIndexMap(citations: V3CitationRow[]): Map<string, number> {
  const out = new Map<string, number>();
  for (const c of citations) {
    if (c.display_index != null) out.set(c.source_id, c.display_index);
  }
  return out;
}

function chartUrl(provenance: Record<string, unknown> | undefined): string | null {
  if (!provenance) return null;
  const url = provenance.url;
  return typeof url === "string" ? url : null;
}

export function V3ReportRenderer({ source }: { source: FileSource }): JSX.Element {
  const [status, setStatus] = useState<Status>("loading");
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reportId = source.kind === "v3_report" ? source.reportId : null;

  const load = useCallback(async () => {
    if (!reportId) return;
    setStatus("loading");
    setError(null);
    try {
      const d = await getV3Run(reportId);
      setDetail(d);
      setStatus("ok");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setStatus("error");
    }
  }, [reportId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!reportId) {
    return (
      <RendererError message="v3 report viewer requires a report id." onRetry={load} />
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

  const displayIndexById = buildDisplayIndexMap(detail.citations);
  const chartById = new Map(detail.charts.map((c) => [c.chart_id, c]));

  return (
    <article
      data-testid="v3-report-renderer"
      className="mx-auto max-w-[680px] px-6 py-6"
    >
      <header className="mb-6 border-b border-[--color-border-subtle] pb-4">
        <h1 className="m-0 text-[22px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
          {detail.report.subject}
        </h1>
        <p className="mt-2 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          {detail.report.template_id} · {detail.report.status} ·{" "}
          {detail.sections.length} section{detail.sections.length === 1 ? "" : "s"}{" "}
          · {detail.charts.length} chart{detail.charts.length === 1 ? "" : "s"} ·{" "}
          {detail.citations.length} source{detail.citations.length === 1 ? "" : "s"}
        </p>
        {detail.error_message ? (
          <p className="mt-2 text-[12.5px] text-[--color-feedback-warning]">
            {detail.error_message}
          </p>
        ) : null}
      </header>

      {detail.sections.map((s) => {
        const rewritten = rewriteCitations(s.markdown, displayIndexById);
        // Split on chart refs so we can interleave the React chart
        // placeholder between markdown chunks. Preserves the section's
        // narrative shape while letting non-text content render.
        const parts = splitOnChartRefs(rewritten);
        return (
          <section
            key={s.section_id}
            data-testid={`v3-report-section-${s.section_id}`}
            className="mb-7"
          >
            <header className="mb-2 flex items-baseline gap-2">
              <h2 className="m-0 text-[17px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
                {s.title}
              </h2>
              {s.version > 1 ? (
                <span
                  data-testid={`v3-report-section-revised-${s.section_id}`}
                  className="font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]"
                >
                  · revised v{s.version}
                </span>
              ) : null}
            </header>
            <div className="prose prose-sm max-w-none text-[14px] leading-[1.7] text-[--color-text-primary] dark:prose-invert">
              {parts.map((part, i) =>
                part.kind === "markdown" ? (
                  <ReactMarkdown key={`md-${i}`} remarkPlugins={[remarkGfm]}>
                    {part.value}
                  </ReactMarkdown>
                ) : (
                  <ChartPlaceholder
                    key={`chart-${part.value}`}
                    chartId={part.value}
                    chart={chartById.get(part.value) ?? null}
                  />
                ),
              )}
            </div>
          </section>
        );
      })}

      {detail.citations.length > 0 ? (
        <section
          data-testid="v3-report-bibliography"
          className="mt-8 border-t border-[--color-border-subtle] pt-4"
        >
          <h2 className="mb-3 text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
            Sources
          </h2>
          <ol className="m-0 space-y-1 pl-0 text-[12.5px] text-[--color-text-secondary]">
            {detail.citations
              .filter((c) => c.display_index != null)
              .sort((a, b) => (a.display_index ?? 0) - (b.display_index ?? 0))
              .map((c) => {
                const url = chartUrl(c.provenance);
                return (
                  <li key={c.source_id} className="list-none">
                    <span className="mr-2 font-mono text-[--color-text-tertiary]">
                      [{c.display_index}]
                    </span>
                    {url ? (
                      <a
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[--color-text-primary] hover:text-[--color-feedback-success]"
                      >
                        {url}
                      </a>
                    ) : (
                      <span className="text-[--color-text-secondary]">
                        {c.tool_name}
                      </span>
                    )}
                    <span className="ml-2 font-mono text-[10.5px] text-[--color-text-tertiary]">
                      {c.source_id}
                    </span>
                  </li>
                );
              })}
          </ol>
        </section>
      ) : null}
    </article>
  );
}

type SplitPart =
  | { kind: "markdown"; value: string }
  | { kind: "chart"; value: string };

function splitOnChartRefs(markdown: string): SplitPart[] {
  const parts: SplitPart[] = [];
  let lastIndex = 0;
  CHART_REF_RE.lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = CHART_REF_RE.exec(markdown)) !== null) {
    if (match.index > lastIndex) {
      parts.push({ kind: "markdown", value: markdown.slice(lastIndex, match.index) });
    }
    parts.push({ kind: "chart", value: match[1] });
    lastIndex = CHART_REF_RE.lastIndex;
  }
  if (lastIndex < markdown.length) {
    parts.push({ kind: "markdown", value: markdown.slice(lastIndex) });
  }
  if (parts.length === 0) {
    parts.push({ kind: "markdown", value: markdown });
  }
  return parts;
}

function ChartPlaceholder({
  chartId,
  chart,
}: {
  chartId: string;
  chart: {
    chart_id: string;
    chart_type: string;
    title: string;
    rendered_url: string | null;
  } | null;
}): JSX.Element {
  return (
    <figure
      data-testid={`v3-report-chart-${chartId}`}
      className="my-4 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] p-3"
    >
      {chart?.rendered_url ? (
        <img
          src={chart.rendered_url}
          alt={chart.title}
          className="mx-auto block max-w-full"
        />
      ) : (
        <div className="flex flex-col items-center justify-center py-6 text-center font-mono text-[11px] text-[--color-text-tertiary]">
          <span>
            [chart: {chartId}
            {chart ? ` · ${chart.chart_type}` : ""}]
          </span>
          {chart?.title ? (
            <span className="mt-1 text-[12px] not-italic text-[--color-text-secondary]">
              {chart.title}
            </span>
          ) : null}
        </div>
      )}
    </figure>
  );
}
