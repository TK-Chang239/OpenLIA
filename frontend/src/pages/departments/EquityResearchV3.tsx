/**
 * v3 equity-research page.
 *
 * Intentionally minimal: a focused form, a submit, a result viewer
 * with sections + bibliography, and links to the HTML / PDF render
 * endpoints. The full chat-style composer that v2.3 grew lives next
 * door (`EquityResearch.tsx`) and stays untouched until v3 is the
 * default.
 *
 * v3 runs are synchronous from the client's perspective — POST blocks
 * until the tool-use loop finishes (typically 1-5 min). Phase 3b will
 * add SSE for incremental progress; for now a clear "Running... this
 * can take a few minutes" message is the right UX given the wait.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/_request";
import {
  type V3Language,
  type V3ReportLength,
  type V3ReportType,
  type V3ReportDetail,
  type V3StartPayload,
  type V3StartResponse,
  getV3Run,
  listV3Runs,
  startV3Run,
  v3HtmlUrl,
  v3PdfUrl,
} from "../../api/equity-research-v3";

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

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [recentRuns, setRecentRuns] = useState<V3ReportDetail["report"][] | null>(null);

  // Reload the recent-runs sidebar on mount and after every successful run.
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

  // Auto-load a run when ?id=<report_id> is present in the URL.
  useEffect(() => {
    if (!reportIdFromUrl) return;
    let cancelled = false;
    (async () => {
      try {
        const d = await getV3Run(reportIdFromUrl);
        if (!cancelled) setDetail(d);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : String(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reportIdFromUrl]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!subject.trim()) return;
      setSubmitting(true);
      setError(null);
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
        const response: V3StartResponse = await startV3Run(payload);
        const detailRow = await getV3Run(response.report_id);
        setDetail(detailRow);
        setSearchParams({ id: response.report_id }, { replace: true });
        refreshRecent();
      } catch (err) {
        if (err instanceof ApiError && err.status === 503) {
          setError(
            "v3 engine disabled on the server. Set REPORT_ENGINE_VERSION=v3 to enable.",
          );
        } else {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        setSubmitting(false);
      }
    },
    [language, length, modelIndex, refreshRecent, reportType, setSearchParams, subject],
  );

  const canSubmit = subject.trim().length > 0 && !submitting;

  return (
    <div className="flex h-full">
      <aside className="w-72 shrink-0 border-r border-zinc-200 bg-zinc-50 overflow-y-auto">
        <RecentRunsSidebar
          rows={recentRuns}
          activeId={detail?.report.report_id ?? reportIdFromUrl}
          onSelect={(id) => setSearchParams({ id }, { replace: true })}
        />
      </aside>
      <main className="flex-1 overflow-y-auto p-6">
        <header className="mb-6">
          <h1 className="text-2xl font-semibold">Equity Research — v3</h1>
          <p className="text-sm text-zinc-600">
            Single-model engine. Runs take ~1–5 minutes; the page blocks until the
            report is complete.
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
              disabled={submitting}
              autoFocus
            />
          </label>

          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Report type</span>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as V3ReportType)}
              className="rounded border border-zinc-300 px-2 py-1.5"
              disabled={submitting}
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
              disabled={submitting}
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
              disabled={submitting}
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
              disabled={submitting}
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
              {submitting ? "Running…" : "Run report"}
            </button>
            {submitting && (
              <span className="text-xs text-zinc-500">
                Researching, computing, and writing. This can take a few minutes — keep
                this tab open.
              </span>
            )}
          </div>
        </form>

        {error && (
          <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 mb-6 max-w-2xl">
            {error}
          </div>
        )}

        {detail && <ReportResult detail={detail} />}
      </main>
    </div>
  );
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
// Result viewer
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
            We render the section body as a preformatted markdown
            preview here so the user gets a quick read inside the SPA.
            Final reader-grade rendering (with charts and resolved
            citations) lives at /html. This is intentional — the SPA
            view favors quick browsing; the canonical view is the
            assembled HTML.
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
