/**
 * V3ChatThread — the in-page conversation surface for a v3 report.
 *
 * Replaces the separate ``V3RevisionChat`` component (PR12). After
 * the user submits the initial prompt, this thread is the only chat
 * surface on the page — every follow-up + revision lands here as the
 * user types in the page's bottom ``ErComposer``, the parent calls
 * ``startV3Revision``, and the thread re-renders.
 *
 * Turn structure:
 *
 *   - one user turn for the initial prompt + the settings snapshot
 *     active when it was submitted
 *   - one system turn for the run itself: ``StreamPanel``-style
 *     live activity while streaming, the ``V3ReportCard`` when the
 *     run reaches a terminal state
 *   - per revision: one user turn (the revision request) + one
 *     system turn (revision status row; the report card at the top
 *     of the thread updates in place as revisions complete)
 *
 * Revisions are polled at 2s while the latest revision is in flight
 * (mirrors the pattern from the deleted V3RevisionChat). The parent
 * is responsible for calling ``onRefreshDetail`` when a revision
 * lands terminal so the card reflects the latest section versions.
 */
import { AlertTriangle, Check, Loader2, User as UserIcon } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import {
  type V3Event,
  type V3ReportDetail,
  type V3Revision,
  cancelV3Revision,
  listV3Revisions,
} from "../../api/equity-research-v3";
import { V3ReportCard } from "./V3ReportCard";

const POLL_INTERVAL_MS = 2000;

/** Settings captured at submit time so the first user message can
 *  render the chips even before ``detail`` loads (and so we don't
 *  lose ``reasoning_effort``, which isn't persisted on the row). */
export interface ChatSettingsSnapshot {
  templateName: string;
  length: string;
  language: string;
  reasoningEffort: string;
  modelLabel: string;
}

interface Props {
  /** The original subject / prompt the user submitted to start the
   *  run. After page reload (no in-memory snapshot) the parent can
   *  source this from ``detail.report.subject``. */
  initialPrompt: string | null;
  /** Settings active when the initial run was dispatched. Null on
   *  page reload when we only have what the row persists; the
   *  fallback renders chips from ``detail.report`` directly. */
  initialSettings: ChatSettingsSnapshot | null;
  /** The active run's report id. ``null`` before the first submit. */
  reportId: string | null;
  /** Live SSE state for the currently-running initial dispatch.
   *  Used by the system turn to render the StreamPanel chips. */
  stream: {
    status: string;
    events: V3Event[];
    sectionsWritten: number;
    chartsEmitted: number;
    toolCallsInflight: number;
    terminalMessage: string | null;
    errorMessage: string | null;
  };
  /** Persisted detail (sections + charts + cover). Populated once
   *  the run reaches a terminal state; the V3ReportCard renders it. */
  detail: V3ReportDetail | null;
  /** Fired when the most-recent revision lands in a terminal state.
   *  Parent re-fetches the report so the latest section versions
   *  render in the card. */
  onRefreshDetail: () => void;
}

function isTerminal(status: V3Revision["status"]): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

export function V3ChatThread({
  initialPrompt,
  initialSettings,
  reportId,
  stream,
  detail,
  onRefreshDetail,
}: Props): JSX.Element | null {
  const [revisions, setRevisions] = useState<V3Revision[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const lastInFlightIdRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    if (!reportId) return;
    try {
      const rows = await listV3Revisions(reportId);
      setRevisions(rows);
      const latest = rows[rows.length - 1];
      if (latest && !isTerminal(latest.status)) {
        lastInFlightIdRef.current = latest.id;
      } else if (
        latest
        && isTerminal(latest.status)
        && lastInFlightIdRef.current === latest.id
      ) {
        lastInFlightIdRef.current = null;
        onRefreshDetail();
      }
    } catch {
      // Transient errors don't block the UI; the next poll recovers.
    }
  }, [reportId, onRefreshDetail]);

  // Initial fetch + re-fetch when the active report changes.
  useEffect(() => {
    setRevisions(null);
    void refresh();
  }, [reportId, refresh]);

  // Poll while a revision is in flight.
  useEffect(() => {
    if (!revisions) return;
    const latest = revisions[revisions.length - 1];
    if (!latest || isTerminal(latest.status)) return;
    const t = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(t);
  }, [revisions, refresh]);

  const handleCancel = async (revisionId: string) => {
    try {
      await cancelV3Revision(revisionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  if (!reportId) return null;

  // Resolve the initial prompt / settings, preferring the live
  // snapshot but falling back to the persisted row so a page reload
  // still shows the first user message correctly.
  const promptText = initialPrompt ?? detail?.report.subject ?? "";
  const settings = initialSettings ?? snapshotFromDetail(detail);

  return (
    <div
      data-testid="er-v3-chat-thread"
      className="mx-auto flex w-full max-w-[760px] flex-col gap-4"
    >
      {/* --- Initial user turn ------------------------------------- */}
      <UserMessage prompt={promptText} settings={settings} />

      {/* --- Initial system turn ----------------------------------- */}
      <SystemTurn>
        {detail ? (
          <V3ReportCard
            detail={detail}
            revising={revisions?.some((r) => !isTerminal(r.status)) ?? false}
          />
        ) : (
          <StreamPanel
            reportId={reportId}
            status={stream.status}
            events={stream.events}
            sectionsWritten={stream.sectionsWritten}
            chartsEmitted={stream.chartsEmitted}
            toolCallsInflight={stream.toolCallsInflight}
            terminalMessage={stream.terminalMessage}
            errorMessage={stream.errorMessage}
          />
        )}
      </SystemTurn>

      {/* --- Per-revision turns ------------------------------------- */}
      {(revisions ?? []).map((rev) => (
        <RevisionTurn
          key={rev.id}
          revision={rev}
          onCancel={() => handleCancel(rev.id)}
        />
      ))}

      {error ? (
        <div
          role="alert"
          data-testid="er-v3-chat-error"
          className="rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
        >
          {error}
        </div>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function UserMessage({
  prompt,
  settings,
}: {
  prompt: string;
  settings: ChatSettingsSnapshot | null;
}): JSX.Element {
  return (
    <article
      data-testid="er-v3-user-message"
      className="ml-auto flex max-w-[640px] flex-col items-end gap-2"
    >
      <div className="flex items-start gap-2">
        <div className="rounded-[12px] rounded-tr-sm bg-[--color-accent-primary] px-4 py-3 text-[14px] leading-[1.55] text-[--color-accent-on]">
          <p className="m-0 whitespace-pre-wrap">{prompt || "(empty prompt)"}</p>
        </div>
        <div
          aria-hidden="true"
          className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-secondary]"
        >
          <UserIcon size={13} strokeWidth={1.7} />
        </div>
      </div>
      {settings ? <SettingsChips settings={settings} /> : null}
    </article>
  );
}

function SettingsChips({
  settings,
}: {
  settings: ChatSettingsSnapshot;
}): JSX.Element {
  const chips: Array<{ label: string; value: string }> = [
    { label: "Template", value: settings.templateName },
    { label: "Length", value: capitalize(settings.length) },
    { label: "Language", value: languageLabel(settings.language) },
    { label: "Reasoning", value: capitalize(settings.reasoningEffort) },
    { label: "Model", value: settings.modelLabel },
  ];
  return (
    <div
      data-testid="er-v3-settings-chips"
      className="flex max-w-[640px] flex-wrap justify-end gap-[6px] pr-9 font-mono text-[10px] tracking-[0.04em] text-[--color-text-tertiary]"
    >
      {chips
        .filter((c) => c.value && c.value.length > 0)
        .map((c) => (
          <span
            key={c.label}
            className="inline-flex items-center gap-[4px] rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-[2px]"
          >
            <span className="uppercase text-[--color-text-tertiary]">
              {c.label}
            </span>
            <span className="text-[--color-text-secondary]">{c.value}</span>
          </span>
        ))}
    </div>
  );
}

function SystemTurn({ children }: { children: React.ReactNode }): JSX.Element {
  return (
    <article
      data-testid="er-v3-system-message"
      className="mr-auto flex w-full max-w-[680px] flex-col gap-2"
    >
      {children}
    </article>
  );
}

function RevisionTurn({
  revision,
  onCancel,
}: {
  revision: V3Revision;
  onCancel: () => void | Promise<void>;
}): JSX.Element {
  return (
    <>
      <UserMessage
        prompt={revision.request}
        // Revisions inherit the original report's settings; show a
        // minimal chip row with the revision index so the turn reads
        // as "revision N" without restating template + length.
        settings={null}
      />
      <article
        data-testid={`er-v3-revision-turn-${revision.id}`}
        className="mr-auto flex max-w-[680px] flex-col gap-2"
      >
        <div className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-2">
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 flex-1 items-center gap-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                Revision #{revision.revision_index}
              </span>
              <RevisionStatusBadge status={revision.status} />
            </div>
            {revision.status === "running" ? (
              <button
                type="button"
                onClick={() => void onCancel()}
                data-testid={`er-v3-revision-cancel-${revision.id}`}
                className="rounded border border-[--color-border-subtle] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-feedback-danger] hover:text-[--color-feedback-danger]"
              >
                Cancel
              </button>
            ) : null}
          </div>
          {revision.error_message ? (
            <p className="mt-1 text-[11.5px] text-[--color-feedback-danger]">
              {revision.error_message}
            </p>
          ) : null}
        </div>
      </article>
    </>
  );
}

function RevisionStatusBadge({
  status,
}: {
  status: V3Revision["status"];
}): JSX.Element {
  const map = {
    running: {
      label: "Running",
      cls: "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary]",
      icon: <Loader2 size={10} strokeWidth={2} className="animate-spin" />,
    },
    completed: {
      label: "Completed",
      cls: "border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]",
      icon: <Check size={10} strokeWidth={2.4} />,
    },
    failed: {
      label: "Failed",
      cls: "border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] text-[--color-feedback-danger]",
      icon: <AlertTriangle size={10} strokeWidth={2} />,
    },
    cancelled: {
      label: "Cancelled",
      cls: "border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] text-[--color-feedback-warning]",
      icon: null,
    },
  }[status];
  return (
    <span
      data-testid="er-v3-revision-status"
      className={`inline-flex items-center gap-[5px] rounded-full border px-2 py-[2px] font-mono text-[9.5px] uppercase tracking-[0.08em] ${map.cls}`}
    >
      {map.icon}
      {map.label}
    </span>
  );
}

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
// Helpers
// ---------------------------------------------------------------------------

const _BUILTIN_TEMPLATE_LABELS: Record<string, string> = {
  initiation_default: "Stock Initiation",
  update_default: "Stock Update",
  sector_research_default: "Sector Research",
};

function snapshotFromDetail(
  detail: V3ReportDetail | null,
): ChatSettingsSnapshot | null {
  if (!detail) return null;
  const r = detail.report;
  // ``reasoning_effort`` isn't persisted on the row today — chip
  // omitted when we can't recover it. Same for the model label
  // (the row carries provider_kind + model strings; without the
  // catalog we just show the model id verbatim).
  return {
    templateName: _BUILTIN_TEMPLATE_LABELS[r.template_id] ?? r.template_id,
    length: r.length,
    language: r.language,
    reasoningEffort: "",
    modelLabel: "",
  };
}

function capitalize(value: string): string {
  if (!value) return "";
  return value.charAt(0).toUpperCase() + value.slice(1);
}

function languageLabel(value: string): string {
  if (value === "zh-TW") return "Chinese (繁體)";
  if (value === "en") return "English";
  return value;
}
