/**
 * v3 equity-research page.
 *
 * Visual shape mirrors the v1/v2 equity-research surface — centered
 * WelcomeStage greeting on first load, bottom-pinned ErComposer for
 * free-form prompts, a model picker pill in the page header, and the
 * Report Settings pill on the WelcomeStage row. Submission goes
 * through the SSE start endpoint (``POST /v3/runs/start``) and the
 * stream lives inside ``useV3RunStream``.
 *
 * v3 takes a free-form ``subject`` (per schemas.py:111 — "either a
 * ticker (RKLB.US) or a free-form topic"), so the composer is in
 * single-textarea mode. No clarify stage; whatever the user types is
 * passed straight through as the subject for the run.
 */
import { type JSX, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/_request";
import {
  type V3Event,
  type V3Language,
  type V3ReportDetail,
  type V3ReportLength,
  type V3ReportSummary,
  type V3ReportType,
  type V3StartPayload,
  getV3Run,
  listV3Runs,
  startV3RunAsync,
  v3HtmlUrl,
  v3PdfUrl,
} from "../../api/equity-research-v3";
import { useAuth } from "../../auth/AuthContext";
import { ErComposer } from "../../components/equity-research/ErComposer";
import { WelcomeStage } from "../../components/equity-research/WelcomeStage";
import {
  V3ModelPicker,
  type V3ModelSelection,
} from "../../components/equity-research-v3/V3ModelPicker";
import { V3ReportSettingsModal } from "../../components/equity-research-v3/V3ReportSettingsModal";
import { useV3RunStream } from "../../components/equity-research-v3/useV3RunStream";

const SETTINGS_LS_KEY = "er.v3.settings";

interface PersistedSettings {
  reportType: V3ReportType;
  length: V3ReportLength;
  language: V3Language;
}

const DEFAULT_SETTINGS: PersistedSettings = {
  reportType: "initiation",
  length: "normal",
  language: "en",
};

function loadSettings(): PersistedSettings {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(SETTINGS_LS_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<PersistedSettings>;
    return {
      reportType: parsed.reportType ?? DEFAULT_SETTINGS.reportType,
      length: parsed.length ?? DEFAULT_SETTINGS.length,
      language: parsed.language ?? DEFAULT_SETTINGS.language,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(next: PersistedSettings): void {
  try {
    window.localStorage.setItem(SETTINGS_LS_KEY, JSON.stringify(next));
  } catch {
    /* localStorage disabled — settings still apply for this session. */
  }
}

function firstName(displayName: string | null | undefined): string {
  if (!displayName) return "there";
  const trimmed = displayName.trim();
  if (!trimmed) return "there";
  return trimmed.split(/\s+/)[0];
}

// v2.2 ReportMode used by the shared WelcomeStage/ErComposer chrome.
// v3 talks in V3ReportType, so we translate at the edges to keep the
// shared chrome rendering a coherent pill label.
function reportTypeToMode(t: V3ReportType): "stock_initiation" | "stock_update" | "sector_research" {
  switch (t) {
    case "initiation":
      return "stock_initiation";
    case "update":
      return "stock_update";
    case "sector_research":
      return "sector_research";
  }
}

export default function EquityResearchV3(): JSX.Element {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const reportIdFromUrl = searchParams.get("id") ?? null;

  const [prompt, setPrompt] = useState("");
  const [settings, setSettings] = useState<PersistedSettings>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [model, setModel] = useState<V3ModelSelection | null>(null);

  const [startError, setStartError] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [activeReportId, setActiveReportId] = useState<string | null>(reportIdFromUrl);
  const [recentRuns, setRecentRuns] = useState<V3ReportSummary[] | null>(null);

  const stream = useV3RunStream(activeReportId);

  const persistSettings = useCallback((next: PersistedSettings) => {
    setSettings(next);
    saveSettings(next);
  }, []);

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
  // detail so the result viewer renders sections + bibliography.
  // Also fires for late-connect runs (?id= with snapshot).
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

  const isStreaming = stream.status === "streaming";

  const handleSubmit = useCallback(
    async (payload: { ticker: string; prompt: string }) => {
      const subject = payload.prompt.trim();
      if (!subject) {
        setStartError("Tell the engine what to research.");
        return;
      }
      if (!model) {
        setStartError("No model selected. Configure one in Settings → Models.");
        return;
      }
      setStartError(null);
      setDetail(null);
      setPrompt("");
      try {
        const body: V3StartPayload = {
          subject,
          language: settings.language,
          length: settings.length,
          report_type: settings.reportType,
          provider_kind: model.provider_kind,
          model: model.model,
        };
        const response = await startV3RunAsync(body);
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
    [model, refreshRecent, settings.language, settings.length, settings.reportType],
  );

  const handleStop = useCallback(() => {
    if (isStreaming) void stream.cancel();
  }, [isStreaming, stream]);

  const handleNewRun = useCallback(() => {
    setActiveReportId(null);
    setDetail(null);
    setStartError(null);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("id");
        return next;
      },
      { replace: true },
    );
  }, [setSearchParams]);

  const mode = reportTypeToMode(settings.reportType);
  const isWelcome = activeReportId === null && detail === null && !isStreaming;
  const placeholder = isWelcome
    ? 'What should this report cover? (e.g., "RKLB.US — initiation, focus on launch cadence")'
    : "Start another v3 report…";

  return (
    <div
      className="flex h-full flex-col bg-[--color-bg-base]"
      data-testid="er-v3-page"
    >
      <div className="flex flex-1 min-h-0 flex-col">
        <div className="flex items-center justify-between gap-2 px-4 pt-3">
          <div className="flex items-center gap-2">
            {!isWelcome ? (
              <button
                type="button"
                onClick={handleNewRun}
                data-testid="er-v3-new-run"
                className="inline-flex items-center gap-[6px] rounded-sm border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-[3px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
              >
                New run
              </button>
            ) : null}
          </div>
          <V3ModelPicker onChange={setModel} />
        </div>

        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          {isWelcome ? (
            <>
              <WelcomeStage
                firstName={firstName(user?.display_name)}
                mode={mode}
                length={settings.length}
                onModeRowClick={() => setSettingsOpen(true)}
              />
              <RecentRunsPanel
                rows={recentRuns}
                onSelect={(id) => setActiveReportId(id)}
              />
            </>
          ) : (
            <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4 px-6 py-6">
              {activeReportId ? (
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
              ) : null}

              {detail ? <ReportResult detail={detail} /> : null}
            </div>
          )}
        </div>

        {startError ? (
          <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 pt-3">
            <div
              role="alert"
              data-testid="er-v3-error"
              className="mx-auto max-w-[760px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
            >
              {startError}
            </div>
          </div>
        ) : null}
      </div>

      <ErComposer
        value={prompt}
        onChange={setPrompt}
        onSubmit={handleSubmit}
        onStop={handleStop}
        isStreaming={isStreaming}
        placeholder={placeholder}
        mode={mode}
        length={settings.length}
        onModeClick={() => setSettingsOpen(true)}
        disabled={model === null}
      />

      <V3ReportSettingsModal
        open={settingsOpen}
        reportType={settings.reportType}
        length={settings.length}
        language={settings.language}
        onReportTypeChange={(v) => persistSettings({ ...settings, reportType: v })}
        onLengthChange={(v) => persistSettings({ ...settings, length: v })}
        onLanguageChange={(v) => persistSettings({ ...settings, language: v })}
        onClose={() => setSettingsOpen(false)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Recent runs (inline panel below welcome) — replaces the old left sidebar
// so the page chrome matches the v1/v2 surface.
// ---------------------------------------------------------------------------

function RecentRunsPanel({
  rows,
  onSelect,
}: {
  rows: V3ReportSummary[] | null;
  onSelect: (id: string) => void;
}): JSX.Element | null {
  if (rows === null) {
    return (
      <div className="mx-auto w-full max-w-[760px] px-4 pb-4 text-[11px] text-[--color-text-tertiary]">
        Loading recent runs…
      </div>
    );
  }
  if (rows.length === 0) return null;
  const shown = rows.slice(0, 6);
  return (
    <div
      data-testid="er-v3-recent-runs"
      className="mx-auto w-full max-w-[760px] px-4 pb-4"
    >
      <h2 className="mb-[8px] font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
        Recent runs
      </h2>
      <ul className="flex flex-col gap-[6px]">
        {shown.map((row) => (
          <li key={row.report_id}>
            <button
              type="button"
              onClick={() => onSelect(row.report_id)}
              data-testid={`er-v3-recent-run-${row.report_id}`}
              className="flex w-full items-center justify-between gap-3 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-2 text-left hover:border-[--color-border-strong]"
            >
              <span className="flex min-w-0 flex-col">
                <span className="truncate text-[13px] font-medium text-[--color-text-primary]">
                  {row.subject}
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                  {row.template_id} · {row.status} · {formatDate(row.created_at)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
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
}): JSX.Element {
  return (
    <section
      data-testid="er-v3-stream-panel"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4"
    >
      <header className="mb-3 flex items-center justify-between">
        <div>
          <h2 className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            Live activity
          </h2>
          <p className="font-mono text-[10.5px] text-[--color-text-tertiary]">
            {reportId}
          </p>
        </div>
        <StatusBadge status={status} />
      </header>

      <dl className="mb-3 grid grid-cols-3 gap-3 text-sm">
        <Chip label="Sections written" value={sectionsWritten} />
        <Chip label="Charts emitted" value={chartsEmitted} />
        <Chip label="Tool calls in flight" value={toolCallsInflight} />
      </dl>

      {terminalMessage ? (
        <p className="mb-2 text-[12px] text-[--color-feedback-warning]">
          {terminalMessage}
        </p>
      ) : null}
      {errorMessage ? (
        <p className="mb-2 text-[12px] text-[--color-feedback-danger]">
          {errorMessage}
        </p>
      ) : null}

      <ol className="max-h-72 space-y-1 overflow-y-auto font-mono text-[11px]">
        {events.length === 0 ? (
          <li className="text-[--color-text-tertiary]">
            Waiting for the first event…
          </li>
        ) : (
          [...events].reverse().map((e, idx) => (
            <li
              key={`${e.type}-${events.length - 1 - idx}`}
              className="text-[--color-text-secondary]"
            >
              <span className="text-[--color-accent-on]">{e.type}</span>{" "}
              <span className="text-[--color-text-tertiary]">
                {summarizePayload(e)}
              </span>
            </li>
          ))
        )}
      </ol>
    </section>
  );
}

function StatusBadge({ status }: { status: string }): JSX.Element {
  const tone =
    {
      streaming:
        "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]",
      completed:
        "border-[--color-feedback-success] bg-[rgba(80,180,80,0.08)] text-[--color-feedback-success]",
      failed:
        "border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] text-[--color-feedback-danger]",
      cancelled:
        "border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] text-[--color-feedback-warning]",
      idle: "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-tertiary]",
    }[status] ??
    "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-tertiary]";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.08em] ${tone}`}
    >
      {status}
    </span>
  );
}

function Chip({ label, value }: { label: string; value: number }): JSX.Element {
  return (
    <div className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2">
      <div className="font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
        {label}
      </div>
      <div className="text-[18px] font-semibold tabular-nums text-[--color-text-primary]">
        {value}
      </div>
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
// Result viewer (shown after the stream reaches a terminal event)
// ---------------------------------------------------------------------------

function ReportResult({ detail }: { detail: V3ReportDetail }): JSX.Element {
  const htmlHref = useMemo(
    () => v3HtmlUrl(detail.report.report_id),
    [detail.report.report_id],
  );
  const pdfHref = useMemo(
    () => v3PdfUrl(detail.report.report_id),
    [detail.report.report_id],
  );

  return (
    <section data-testid="er-v3-result">
      <header className="mb-4 border-b border-[--color-border-subtle] pb-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-[18px] font-semibold text-[--color-text-primary]">
            {detail.report.subject}
          </h2>
          <div className="flex gap-2">
            <a
              href={htmlHref}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-[--color-border-subtle] px-3 py-1 text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
            >
              Open HTML
            </a>
            <a
              href={pdfHref}
              target="_blank"
              rel="noopener noreferrer"
              className="rounded-md border border-[--color-border-subtle] px-3 py-1 text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
            >
              Download PDF
            </a>
          </div>
        </div>
        <div className="mt-1 font-mono text-[10.5px] text-[--color-text-tertiary]">
          Template: {detail.report.template_id} · Status: {detail.report.status} ·{" "}
          {detail.sections.length} sections · {detail.charts.length} charts ·{" "}
          {detail.citations.length} citations
        </div>
        {detail.error_message ? (
          <div className="mt-2 text-[12px] text-[--color-feedback-warning]">
            {detail.error_message}
          </div>
        ) : null}
      </header>

      {detail.sections.map((s) => (
        <article key={s.section_id} className="mb-6">
          <h3 className="mb-1 text-[15px] font-semibold text-[--color-text-primary]">
            {s.title}
          </h3>
          <pre className="whitespace-pre-wrap rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] p-3 text-[12.5px] leading-[1.55] text-[--color-text-secondary]">
            {s.markdown}
          </pre>
        </article>
      ))}

      {detail.citations.length > 0 ? (
        <section className="mt-6 border-t border-[--color-border-subtle] pt-3">
          <h3 className="mb-2 text-[13px] font-semibold text-[--color-text-primary]">
            Sources
          </h3>
          <ol className="space-y-1 text-[11.5px] text-[--color-text-secondary]">
            {detail.citations
              .filter((c) => c.display_index !== null)
              .sort((a, b) => (a.display_index ?? 0) - (b.display_index ?? 0))
              .map((c) => (
                <li key={c.source_id}>
                  <span className="font-medium">[{c.display_index}]</span>{" "}
                  <code className="text-[--color-text-tertiary]">
                    {c.source_id}
                  </code>{" "}
                  {c.tool_name}
                </li>
              ))}
          </ol>
        </section>
      ) : null}
    </section>
  );
}
