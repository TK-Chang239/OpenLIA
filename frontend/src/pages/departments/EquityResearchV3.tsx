/**
 * v3 equity-research page.
 *
 * Submits via the streaming entrypoint: POST /v3/runs/start returns
 * a report_id immediately; the page connects an EventSource to the
 * matching /events endpoint via ``useV3RunStream`` and shows live
 * activity until the terminal event lands. Cancel button is wired
 * to POST /v3/runs/{id}/cancel.
 *
 * Once the stream closes (run.completed / failed / cancelled /
 * snapshot) the page fetches the full persisted detail and
 * surfaces the result viewer with "Open HTML" / "Download PDF"
 * buttons. The chat-style composer that v2.3 grew lives next door
 * (``EquityResearch.tsx``) and stays untouched.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/_request";
import {
  type V3Event,
  type V3Language,
  type V3ReportDetail,
  type V3ReportLength,
  type V3ReportType,
  type V3StartPayload,
  getV3Run,
  listV3Runs,
  startV3RunAsync,
  v3HtmlUrl,
  v3PdfUrl,
} from "../../api/equity-research-v3";
import { useV3RunStream } from "../../components/equity-research-v3/useV3RunStream";

// ---------------------------------------------------------------------------
// Static option lists
// ---------------------------------------------------------------------------

const REPORT_TYPES: { value: V3ReportType; label: string }[] = [
  { value: "initiation", label: "Stock Initiation" },
  { value: "update", label: "Stock Update" },
  { value: "sector_research", label: "Sector Research" },
];

const LENGTHS: { value: V3ReportLength; label: string }[] = [
  { value: "concise", label: "Concise" },
  { value: "normal", label: "Normal" },
  { value: "elaborative", label: "Elaborative" },
];

const LANGUAGES: { value: V3Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "zh-TW", label: "繁體中文" },
];

// Models the v3 capability gate accepts (must advertise
// `web_search_native`). Add new models here as the capability map
// grows server-side.
const PROVIDER_MODELS: { provider_kind: string; model: string; label: string }[] = [
  {
    provider_kind: "anthropic",
    model: "claude-sonnet-4-6",
    label: "Anthropic — claude-sonnet-4-6",
  },
  {
    provider_kind: "openai",
    model: "gpt-5.4-2026-03-05",
    label: "OpenAI — gpt-5.4",
  },
  { provider_kind: "gemini", model: "gemini-3.1-pro", label: "Google — gemini-3.1-pro" },
];

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function EquityResearchV3() {
  const [searchParams, setSearchParams] = useSearchParams();
  const reportIdFromUrl = searchParams.get("id") ?? null;

  const [subject, setSubject] = useState("");
  const [reportType, setReportType] = useState<V3ReportType>("initiation");
  const [length, setLength] = useState<V3ReportLength>("normal");
  const [language, setLanguage] = useState<V3Language>("en");
  const [modelIndex, setModelIndex] = useState(0);

  const [startError, setStartError] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [activeReportId, setActiveReportId] = useState<string | null>(reportIdFromUrl);
  const [recentRuns, setRecentRuns] = useState<V3ReportDetail["report"][] | null>(null);

  const stream = useV3RunStream(activeReportId);

  const refreshRecent = useCallback(async () => {
    try {
      const rows = await listV3Runs();
      setRecentRuns(rows);
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setRecentRuns([]);
      }
    }
  }, []);

  useEffect(() => {
    refreshRecent();
  }, [refreshRecent]);

  // When the stream reaches a terminal state, fetch the persisted
  // detail so the result viewer can render the full sections +
  // bibliography. Also re-fetch when the user opens an existing
  // run via ?id= (stream emits run.snapshot then closes).
  useEffect(() => {
    if (!activeReportId) {
      setDetail(null);
      return;
    }
    if (stream.status !== "streaming" && stream.status !== "idle") {
      let cancelled = false;
      (async () => {
        try {
          const d = await getV3Run(activeReportId);
          if (!cancelled) {
            setDetail(d);
            refreshRecent();
          }
        } catch (err) {
          if (cancelled) return;
          setStartError(err instanceof Error ? err.message : String(err));
        }
      })();
      return () => {
        cancelled = true;
      };
    }
  }, [activeReportId, refreshRecent, stream.status]);

  // Keep ?id= in the URL synced to whichever run we're watching.
  useEffect(() => {
    if (activeReportId && activeReportId !== reportIdFromUrl) {
      setSearchParams({ id: activeReportId }, { replace: true });
    }
  }, [activeReportId, reportIdFromUrl, setSearchParams]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!subject.trim()) return;
      setStartError(null);
      setDetail(null);
      try {
        const payload: V3StartPayload = {
          subject: subject.trim(),
          language,
          length,
          report_type: reportType,
          provider_kind: PROVIDER_MODELS[modelIndex].provider_kind,
          model: PROVIDER_MODELS[modelIndex].model,
        };
        const response = await startV3RunAsync(payload);
        setActiveReportId(response.report_id);
        refreshRecent();
      } catch (err) {
        if (err instanceof ApiError && err.status === 503) {
          setStartError(
            "v3 engine disabled on the server. Set REPORT_ENGINE_VERSION=v3 to enable.",
          );
        } else {
          setStartError(err instanceof Error ? err.message : String(err));
        }
      }
    },
    [language, length, modelIndex, refreshRecent, reportType, subject],
  );

  const isStreaming = stream.status === "streaming";
  const canSubmit = subject.trim().length > 0 && !isStreaming;

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-zinc-200 bg-zinc-50 overflow-y-auto">
        <RecentRunsSidebar
          rows={recentRuns}
          activeId={activeReportId}
          onSelect={(id) => setActiveReportId(id)}
        />
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold">Equity Research — v3</h1>
          <p className="text-sm text-zinc-600">
            Single-model engine. Live progress streams below; cancel any time.
          </p>
        </header>

        <form
          onSubmit={handleSubmit}
          className="grid grid-cols-2 gap-4 mb-8 max-w-2xl"
        >
          <label className="col-span-2 flex flex-col text-sm">
            <span className="font-medium mb-1">Subject (ticker or topic)</span>
            <input
              type="text"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="RKLB.US"
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={isStreaming}
              autoFocus
            />
          </label>

          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Report type</span>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as V3ReportType)}
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={isStreaming}
            >
              {REPORT_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Length</span>
            <select
              value={length}
              onChange={(e) => setLength(e.target.value as V3ReportLength)}
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={isStreaming}
            >
              {LENGTHS.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Language</span>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value as V3Language)}
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={isStreaming}
            >
              {LANGUAGES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Model</span>
            <select
              value={modelIndex}
              onChange={(e) => setModelIndex(Number(e.target.value))}
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={isStreaming}
            >
              {PROVIDER_MODELS.map((m, i) => (
                <option key={`${m.provider_kind}/${m.model}`} value={i}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>

          <div className="col-span-2 flex items-center gap-3">
            <button
              type="submit"
              disabled={!canSubmit}
              className="rounded bg-indigo-600 text-white px-4 py-1.5 text-sm font-medium disabled:opacity-50"
            >
              {isStreaming ? "Streaming…" : "Run report"}
            </button>
            {isStreaming && (
              <button
                type="button"
                onClick={stream.cancel}
                className="rounded border border-zinc-300 px-3 py-1.5 text-xs"
              >
                Cancel
              </button>
            )}
          </div>
        </form>

        {startError && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 mb-6 max-w-2xl">
            {startError}
          </div>
        )}

        {activeReportId && (
          <StreamPanel
            reportId={activeReportId}
            status={stream.status}
            events={stream.events}
            sectionsWritten={stream.sectionsWritten}
            chartsEmitted={stream.chartsEmitted}
            toolCallsInflight={stream.toolCallsInflight}
            terminalMessage={stream.terminalMessage}
            errorMessage={stream.errorMessage}
          />
        )}

        {detail && <ReportResult detail={detail} />}
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Live activity feed (visible while streaming + after terminal)
// ---------------------------------------------------------------------------

function StreamPanel({
  reportId,
  status,
  events,
  sectionsWritten,
  chartsEmitted,
  toolCallsInflight,
  terminalMessage,
  errorMessage,
}: {
  reportId: string;
  status: string;
  events: V3Event[];
  sectionsWritten: number;
  chartsEmitted: number;
  toolCallsInflight: number;
  terminalMessage: string | null;
  errorMessage: string | null;
}) {
  return (
    <section className="mb-8 max-w-4xl rounded border border-zinc-200 bg-white p-4">
      <header className="flex items-center justify-between mb-3">
        <div>
          <h2 className="text-sm font-semibold uppercase text-zinc-600">
            Live activity
          </h2>
          <p className="text-xs text-zinc-500 font-mono">{reportId}</p>
        </div>
        <StatusBadge status={status} />
      </header>

      <dl className="grid grid-cols-3 gap-3 mb-3 text-sm">
        <Chip label="Sections written" value={sectionsWritten} />
        <Chip label="Charts emitted" value={chartsEmitted} />
        <Chip label="Tool calls in flight" value={toolCallsInflight} />
      </dl>

      {terminalMessage && (
        <p className="text-xs text-amber-700 mb-2">{terminalMessage}</p>
      )}
      {errorMessage && (
        <p className="text-xs text-red-700 mb-2">{errorMessage}</p>
      )}

      <ol className="max-h-72 overflow-y-auto text-xs font-mono space-y-1">
        {events.length === 0 ? (
          <li className="text-zinc-500">Waiting for the first event…</li>
        ) : (
          // Reverse so newest is at top — easier to read in real time.
          [...events].reverse().map((e, idx) => (
            <li key={`${e.type}-${events.length - 1 - idx}`} className="text-zinc-700">
              <span className="text-indigo-600">{e.type}</span>{" "}
              <span className="text-zinc-500">{summarizePayload(e)}</span>
            </li>
          ))
        )}
      </ol>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = {
    streaming: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
    cancelled: "bg-amber-100 text-amber-800",
    idle: "bg-zinc-100 text-zinc-700",
  }[status] ?? "bg-zinc-100 text-zinc-700";
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${tone}`}>
      {status}
    </span>
  );
}

function Chip({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded bg-zinc-50 border border-zinc-200 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-zinc-500">
        {label}
      </div>
      <div className="text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function summarizePayload(event: V3Event): string {
  switch (event.type) {
    case "run.started":
      return `${event.payload.subject} — ${event.payload.model}`;
    case "tool.called":
      return `turn ${event.payload.turn} → ${event.payload.tool_name}`;
    case "tool.completed": {
      const ok = event.payload.ok ? "ok" : "error";
      const sid = event.payload.source_id ? ` ${event.payload.source_id}` : "";
      return `turn ${event.payload.turn} ← ${event.payload.tool_name} (${ok})${sid}`;
    }
    case "section.written":
      return `${event.payload.section_id} (${event.payload.char_count ?? "?"} chars)`;
    case "chart.emitted":
      return `${event.payload.chart_id} (${event.payload.chart_type})`;
    case "run.completed":
    case "run.failed":
    case "run.cancelled":
      return `${event.payload.section_count ?? 0} sections · ${event.payload.chart_count ?? 0} charts · ${event.payload.citation_count ?? 0} citations`;
    case "run.snapshot":
      return `prior run status: ${event.payload.status}`;
    default:
      return "";
  }
}

// ---------------------------------------------------------------------------
// Recent runs sidebar
// ---------------------------------------------------------------------------

function RecentRunsSidebar({
  rows,
  activeId,
  onSelect,
}: {
  rows: V3ReportDetail["report"][] | null;
  activeId: string | null;
  onSelect: (id: string) => void;
}) {
  if (rows === null) {
    return <p className="p-4 text-xs text-zinc-500">Loading…</p>;
  }
  if (rows.length === 0) {
    return (
      <p className="p-4 text-xs text-zinc-500">
        No v3 reports yet. Submit one on the right.
      </p>
    );
  }
  return (
    <ol className="p-2">
      {rows.map((row) => {
        const active = row.report_id === activeId;
        return (
          <li key={row.report_id}>
            <button
              type="button"
              onClick={() => onSelect(row.report_id)}
              className={`w-full text-left px-2 py-2 rounded text-xs ${
                active ? "bg-indigo-100 text-indigo-900" : "hover:bg-zinc-100"
              }`}
            >
              <div className="font-medium truncate">{row.subject}</div>
              <div className="text-zinc-500">
                {row.template_id} · {row.status}
              </div>
              <div className="text-zinc-400">{formatDate(row.created_at)}</div>
            </button>
          </li>
        );
      })}
    </ol>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Result viewer (shown after the stream reaches a terminal event)
// ---------------------------------------------------------------------------

function ReportResult({ detail }: { detail: V3ReportDetail }) {
  const htmlHref = useMemo(() => v3HtmlUrl(detail.report.report_id), [detail.report.report_id]);
  const pdfHref = useMemo(() => v3PdfUrl(detail.report.report_id), [detail.report.report_id]);

  return (
    <section className="max-w-4xl">
      <header className="mb-4 border-b border-zinc-300 pb-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xl font-semibold">{detail.report.subject}</h2>
          <div className="flex gap-2">
            <a
              href={htmlHref}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded border border-zinc-300 px-3 py-1 text-xs"
            >
              Open HTML
            </a>
            <a
              href={pdfHref}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded border border-zinc-300 px-3 py-1 text-xs"
            >
              Download PDF
            </a>
          </div>
        </div>
        <div className="text-xs text-zinc-500 mt-1">
          Template: {detail.report.template_id} · Status: {detail.report.status} ·{" "}
          {detail.sections.length} sections · {detail.charts.length} charts ·{" "}
          {detail.citations.length} citations
        </div>
        {detail.error_message && (
          <div className="mt-2 text-xs text-amber-700">{detail.error_message}</div>
        )}
      </header>

      {detail.sections.map((s) => (
        <article key={s.section_id} className="mb-6">
          <h3 className="text-lg font-semibold mb-1">{s.title}</h3>
          {/*
            Pre-formatted markdown preview here so the user gets a
            quick read inside the SPA. Canonical reader-grade view
            (with charts and resolved citations) is at /html.
          */}
          <pre className="whitespace-pre-wrap text-sm bg-zinc-50 border border-zinc-200 rounded p-3">
            {s.markdown}
          </pre>
        </article>
      ))}

      {detail.citations.length > 0 && (
        <section className="border-t border-zinc-300 pt-3 mt-6">
          <h3 className="text-base font-semibold mb-2">Sources</h3>
          <ol className="text-xs space-y-1">
            {detail.citations
              .filter((c) => c.display_index !== null)
              .sort((a, b) => (a.display_index ?? 0) - (b.display_index ?? 0))
              .map((c) => (
                <li key={c.source_id}>
                  <span className="font-medium">[{c.display_index}]</span>{" "}
                  <code className="text-zinc-500">{c.source_id}</code> {c.tool_name}
                </li>
              ))}
          </ol>
        </section>
      )}
    </section>
  );
}
