/**
 * v3 equity-research page.
 *
 * Visual shape mirrors the v1/v2 equity-research surface — centered
 * WelcomeStage greeting on first load, bottom-pinned ErComposer for
 * free-form prompts, the model picker pill in the composer toolbar,
 * and the Report Settings pill on the WelcomeStage row. Submission
 * goes through the SSE start endpoint (``POST /v3/runs/start``) and
 * the stream lives inside ``useV3RunStream``.
 *
 * v3 takes a free-form ``subject`` (per schemas.py:111 — "either a
 * ticker (RKLB.US) or a free-form topic"), so the composer is in
 * single-textarea mode. No clarify stage; whatever the user types is
 * passed straight through as the subject for the run.
 *
 * The page also registers with ``useChatHeaderRegistry`` so the
 * global TopBar shows the same breadcrumb + history dropdown the
 * v1/v2 page does. Since v3 has no chat-session model, we plug a
 * v3-specific ``V3RunsPopover`` into the registry's ``renderPopover``
 * slot — each run row maps to its report_id.
 */
import { type JSX, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { ApiError } from "../../api/_request";
import {
  type V3Event,
  type V3ReportDetail,
  type V3StartPayload,
  getV3Run,
  startV3RunAsync,
} from "../../api/equity-research-v3";
import { useAuth } from "../../auth/AuthContext";
import { ErComposer } from "../../components/equity-research/ErComposer";
import { WelcomeStage } from "../../components/equity-research/WelcomeStage";
import {
  V3ModelPicker,
  type V3ModelSelection,
} from "../../components/equity-research-v3/V3ModelPicker";
import {
  V3ReportSettingsModal,
  type V3SettingsValue,
} from "../../components/equity-research-v3/V3ReportSettingsModal";
import { V3ReportCard } from "../../components/equity-research-v3/V3ReportCard";
import { V3RevisionChat } from "../../components/equity-research-v3/V3RevisionChat";
import { V3RunsPopover } from "../../components/equity-research-v3/V3RunsPopover";
import { V3TemplateUploadModal } from "../../components/equity-research-v3/V3TemplateUploadModal";
import { useV3RunStream } from "../../components/equity-research-v3/useV3RunStream";
import { useChatHeaderRegistry } from "../../layouts/ChatHeaderContext";

const SETTINGS_LS_KEY = "er.v3.settings";

const DEFAULT_SETTINGS: V3SettingsValue = {
  length: "normal",
  language: "en",
  reasoningEffort: "medium",
  // The seeded built-in for initiation reports. The picker is the
  // only place templates change, so this default is what new users
  // see on the WelcomeStage pill before opening settings.
  templateId: "initiation_default",
  templateName: "Stock Initiation",
};

function loadSettings(): V3SettingsValue {
  if (typeof window === "undefined") return DEFAULT_SETTINGS;
  try {
    const raw = window.localStorage.getItem(SETTINGS_LS_KEY);
    if (!raw) return DEFAULT_SETTINGS;
    const parsed = JSON.parse(raw) as Partial<V3SettingsValue>;
    return {
      length: parsed.length ?? DEFAULT_SETTINGS.length,
      language: parsed.language ?? DEFAULT_SETTINGS.language,
      reasoningEffort:
        parsed.reasoningEffort ?? DEFAULT_SETTINGS.reasoningEffort,
      templateId: parsed.templateId ?? DEFAULT_SETTINGS.templateId,
      templateName: parsed.templateName ?? DEFAULT_SETTINGS.templateName,
    };
  } catch {
    return DEFAULT_SETTINGS;
  }
}

function saveSettings(next: V3SettingsValue): void {
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

// The shared WelcomeStage/ErComposer chrome still requires a
// ``mode: ReportMode`` prop for v1/v2 callers. v3 doesn't track
// report type as a separate concept (templates ARE the report type),
// so the pill label comes from ``templateLabel`` and ``mode`` is set
// to a safe constant.
const V3_MODE_FOR_SHARED_CHROME = "stock_initiation" as const;

export default function EquityResearchV3(): JSX.Element {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const reportIdFromUrl = searchParams.get("id") ?? null;

  const [prompt, setPrompt] = useState("");
  const [settings, setSettings] = useState<V3SettingsValue>(() => loadSettings());
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [model, setModel] = useState<V3ModelSelection | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [templatesRefreshKey, setTemplatesRefreshKey] = useState(0);

  const [startError, setStartError] = useState<string | null>(null);
  const [detail, setDetail] = useState<V3ReportDetail | null>(null);
  const [activeReportId, setActiveReportId] = useState<string | null>(reportIdFromUrl);
  // Keep the active run's subject so the TopBar breadcrumb can render
  // it as a chat-title equivalent. Updated when the page learns the
  // subject (either fresh dispatch or detail fetch).
  const [activeSubject, setActiveSubject] = useState<string | null>(null);

  const stream = useV3RunStream(activeReportId);

  const persistSettings = useCallback((next: V3SettingsValue) => {
    setSettings(next);
    saveSettings(next);
  }, []);

  // When the stream reaches a terminal state, fetch the persisted
  // detail so the result viewer renders sections + bibliography.
  // Also fires for late-connect runs (?id= with snapshot).
  useEffect(() => {
    if (!activeReportId) {
      setDetail(null);
      setActiveSubject(null);
      return;
    }
    if (stream.status !== "streaming" && stream.status !== "idle") {
      let cancelled = false;
      (async () => {
        try {
          const d = await getV3Run(activeReportId);
          if (!cancelled) {
            setDetail(d);
            setActiveSubject(d.report.subject);
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
  }, [activeReportId, stream.status]);

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
      setActiveSubject(subject);
      try {
        const body: V3StartPayload = {
          subject,
          language: settings.language,
          length: settings.length,
          // template_id is the single source of truth — v3 doesn't
          // ship a separate report_type concept anymore. Built-ins
          // (initiation_default etc.) and user uploads both resolve
          // through the same path.
          template_id: settings.templateId,
          provider_kind: model.provider_kind,
          model: model.model,
          // Wire enum is "medium" | "high" only; off → null so the
          // server's ReasoningEffort field stays None and the
          // adapter skips the reasoning param entirely.
          reasoning_effort:
            settings.reasoningEffort === "off" ? null : settings.reasoningEffort,
        };
        const response = await startV3RunAsync(body);
        setActiveReportId(response.report_id);
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
    [
      model,
      settings.language,
      settings.length,
      settings.reasoningEffort,
      settings.templateId,
    ],
  );

  const handleStop = useCallback(() => {
    if (isStreaming) void stream.cancel();
  }, [isStreaming, stream]);

  const handleNewRun = useCallback(() => {
    setActiveReportId(null);
    setDetail(null);
    setActiveSubject(null);
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

  const handleSelectRun = useCallback(
    (runId: string) => {
      if (runId === activeReportId) return;
      setActiveReportId(runId);
      setDetail(null);
      setActiveSubject(null);
      setStartError(null);
    },
    [activeReportId],
  );

  // Reach for ?id= on first paint when present, so the dropdown row
  // for a freshly-loaded URL shows up highlighted. We don't need a
  // separate effect because `activeReportId` is already seeded from
  // reportIdFromUrl above; this is just a no-op safety guard.

  // Register the chat-header so the global TopBar renders the v3
  // history dropdown + "New chat" button. The renderPopover slot
  // plugs the v3-specific runs list in; TopBar stays generic.
  const { register, clear } = useChatHeaderRegistry();
  useEffect(() => {
    register({
      departmentId: "equity_research_v3",
      activeSessionId: activeReportId,
      chatTitle: activeSubject ?? "New chat",
      onSelect: handleSelectRun,
      onCreate: handleNewRun,
      renderPopover: (props) => (
        <V3RunsPopover
          activeSessionId={props.activeSessionId}
          onSelect={props.onSelect}
          onActiveDeleted={props.onActiveDeleted}
          onClose={props.onClose}
        />
      ),
    });
    return () => clear();
  }, [
    activeReportId,
    activeSubject,
    clear,
    handleNewRun,
    handleSelectRun,
    register,
  ]);

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
        <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
          {isWelcome ? (
            <WelcomeStage
              firstName={firstName(user?.display_name)}
              mode={V3_MODE_FOR_SHARED_CHROME}
              length={settings.length}
              onModeRowClick={() => setSettingsOpen(true)}
              templateLabel={settings.templateName}
            />
          ) : (
            <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4 px-6 py-6">
              {activeReportId ? (
                <StreamPanel
                  reportId={activeReportId}
                  subject={activeSubject}
                  status={stream.status}
                  events={stream.events}
                  sectionsWritten={stream.sectionsWritten}
                  chartsEmitted={stream.chartsEmitted}
                  toolCallsInflight={stream.toolCallsInflight}
                  terminalMessage={stream.terminalMessage}
                  errorMessage={stream.errorMessage}
                />
              ) : null}

              {detail ? (
                <>
                  <V3ReportCard
                    detail={detail}
                    revising={detail.report.status === "revising"}
                  />
                  <SectionPreview detail={detail} />
                  <V3RevisionChat
                    reportId={detail.report.report_id}
                    parentRunning={detail.report.status === "running"}
                    onRevisionComplete={() => {
                      // Re-fetch the full detail so the latest
                      // section/chart versions land in the card.
                      void (async () => {
                        try {
                          const d = await getV3Run(detail.report.report_id);
                          setDetail(d);
                        } catch {
                          /* surface via existing error path on next render */
                        }
                      })();
                    }}
                  />
                </>
              ) : null}
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
        mode={V3_MODE_FOR_SHARED_CHROME}
        length={settings.length}
        onModeClick={() => setSettingsOpen(true)}
        modelPicker={<V3ModelPicker onChange={setModel} />}
        disabled={model === null}
        templateLabel={settings.templateName}
      />

      <V3ReportSettingsModal
        open={settingsOpen}
        value={settings}
        onClose={() => setSettingsOpen(false)}
        onSave={persistSettings}
        onUploadClick={() => {
          setSettingsOpen(false);
          setUploadOpen(true);
        }}
        templatesRefreshKey={templatesRefreshKey}
      />

      <V3TemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onSaved={(created) => {
          // Auto-select the newly uploaded template + reopen settings
          // so the user sees their pick land in the list.
          persistSettings({
            ...settings,
            templateId: created.id,
            templateName: created.name,
          });
          setTemplatesRefreshKey((k) => k + 1);
          setSettingsOpen(true);
        }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Live activity feed (visible while streaming + after terminal)
// ---------------------------------------------------------------------------

function StreamPanel({
  reportId,
  subject,
  status,
  events,
  sectionsWritten,
  chartsEmitted,
  toolCallsInflight,
  terminalMessage,
  errorMessage,
}: {
  reportId: string;
  subject: string | null;
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
            Live activity {subject ? `· ${subject}` : ""}
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

function SectionPreview({ detail }: { detail: V3ReportDetail }): JSX.Element {
  return (
    <section data-testid="er-v3-section-preview" className="max-w-[640px]">
      {detail.error_message ? (
        <div className="mb-3 rounded-md border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.06)] px-3 py-2 text-[12px] text-[--color-feedback-warning]">
          {detail.error_message}
        </div>
      ) : null}

      {detail.sections.map((s) => (
        <article key={s.section_id} className="mb-6">
          <header className="mb-1 flex items-center gap-2">
            <h3 className="m-0 text-[15px] font-semibold text-[--color-text-primary]">
              {s.title}
            </h3>
            {s.version > 1 ? (
              <span
                data-testid={`er-v3-section-revised-${s.section_id}`}
                title={`Last touched in revision v${s.version}`}
                className="inline-flex items-center gap-[4px] rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-[1px] font-mono text-[9.5px] uppercase tracking-[0.08em] text-[--color-text-secondary]"
              >
                Revised v{s.version}
              </span>
            ) : null}
          </header>
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
                  <code className="text-[--color-text-tertiary]">{c.source_id}</code>{" "}
                  {c.tool_name}
                </li>
              ))}
          </ol>
        </section>
      ) : null}
    </section>
  );
}
