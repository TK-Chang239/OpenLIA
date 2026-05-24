/**
 * V23Composer — minimal v2.3 equity-research composer.
 *
 * Single textarea + tickers + send button. Starts a v2.3 run, polls
 * /runs/{id} while the run is RUNNING, and surfaces:
 *
 *   - clarify questions when the run suspends in WAITING_ON_USER
 *   - current stage while RUNNING
 *   - last_error on FAILED
 *
 * Intentionally compact — this is the first cut of the v2.3 surface
 * area, not a feature-complete replacement for the v2.2 composer. It
 * exists to drive the engine end-to-end through real models and prove
 * the per-user assignments + persistence + clarify round-trip work in
 * a browser. Richer UX (report renderer, history, retries) follows.
 */
import { AlertTriangle, Download } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import type { ReportLength, ReportMode } from "../../api/equity-research";
import type { AssignmentsResponse } from "../../api/er-v2-3-models";
import {
  type V23ReportType,
  type V23RunPayload,
  type V23RunState,
  type V23Stage,
  getV23Run,
  getV23RunPayload,
  streamV23Answer,
  streamV23Run,
  v23DocxUrl,
} from "../../api/equity-research-v2-3";
import { UserBubble } from "../chat/UserBubble";
import { type ComposerSubmitPayload, ErComposer } from "./ErComposer";
import { V23ClarifyModal } from "./V23ClarifyModal";
import { V23FailedReportCard } from "./V23FailedReportCard";
import { V23RepoPanel } from "./V23RepoPanel";
import { V23ReportCard } from "./V23ReportCard";
import { V23StageStrip } from "./V23StageStrip";
import { WelcomeStage } from "./WelcomeStage";

// v2.2 ReportMode -> v2.3 ReportType. v2.3 also offers morning_brief
// and earnings_review which v2.2 doesn't model — defer surfacing
// those until the Report Settings modal learns about v2.3 modes.
const MODE_TO_V23_TYPE: Record<ReportMode, V23ReportType> = {
  stock_initiation: "initiation",
  stock_update: "update",
  sector_research: "initiation",
};

const STAGE_LABEL: Record<V23Stage, string> = {
  clarify: "Clarifying",
  plan: "Planning",
  research: "Researching",
  compute: "Computing valuation",
  synthesize: "Synthesizing thesis",
  write: "Writing sections",
  visualize: "Validating charts",
  verify: "Verifying",
};

// Pipeline execution order, used to (a) decide which stages to mark
// complete on reattach (everything before the persisted current_stage)
// and (b) infer the failed slot when the engine reports a terminal
// failure without naming the slot. Keep in sync with V23StageStrip.
const STAGE_ORDER: readonly V23Stage[] = [
  "clarify",
  "plan",
  "research",
  "compute",
  "synthesize",
  "write",
  "visualize",
  "verify",
];

interface Props {
  /** When set, the composer hydrates from this run id on mount via
   *  GET /runs/{id}. Used by the page to reattach a run after a page
   *  reload (URL carries ?run_id_v23=<id>). */
  initialRunId?: string | null;
  /** Notify the parent whenever the active run changes — on terminal
   *  state from SSE (we learn the run_id then), on reattach, or when the
   *  user starts a fresh run (id reset to null). Parent mirrors this to
   *  the URL so a reload restores the same view. */
  onRunIdChange?: (runId: string | null) => void;
  /** Fired when the user clicks "Open Report" on a completed run; the
   *  page sets ?view=report so the full-screen overlay mounts. */
  onOpenReport?: (runId: string) => void;
  /** Fired when the user picks a past run from the repo panel; the
   *  page mirrors this into ?run_id_v23=<id> which triggers the
   *  composer's own reattach effect on the next render. */
  onSelectPastRun?: (runId: string) => void;
  /** Engine model assignments snapshot, sourced from the
   *  V23EngineModelsPicker that now lives in the page header. When
   *  null the composer assumes the picker is still loading and keeps
   *  the run button disabled with a generic prompt. */
  assignments?: AssignmentsResponse | null;
  /** v2.2 ReportMode + ReportLength threaded through to the shared
   *  WelcomeStage/ErComposer chrome. The composer maps mode -> v2.3
   *  report_type on submit so the engine respects the user's choice. */
  mode: ReportMode;
  length: ReportLength;
  /** User's display name for the welcome greeting. */
  firstName: string;
  /** Open the Report Settings modal — wired by the page. */
  onModeClick: () => void;
}

export function V23Composer({
  initialRunId = null,
  onRunIdChange,
  onOpenReport,
  onSelectPastRun,
  assignments = null,
  mode,
  length,
  firstName,
  onModeClick,
}: Props): JSX.Element {
  const [prompt, setPrompt] = useState("");
  const [tickerInput, setTickerInput] = useState("");
  const [run, setRun] = useState<V23RunState | null>(null);
  const [stage, setStage] = useState<V23Stage | null>(null);
  const [completedStages, setCompletedStages] = useState<Set<V23Stage>>(
    () => new Set(),
  );
  const [failedStage, setFailedStage] = useState<V23Stage | null>(null);
  // Captured at submit time so we can render a UserBubble immediately
  // (the SSE state frame that carries run.raw_prompt only lands on
  // terminal status). On reattach, run.raw_prompt fills these in.
  const [submittedPrompt, setSubmittedPrompt] = useState<string | null>(null);
  const [submittedTickers, setSubmittedTickers] = useState<string[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  // Tracks whether the user has dismissed the clarify modal for the
  // current waiting_on_user phase so we know whether to render the
  // "Continue clarifying" pill in place of the modal itself.
  const [clarifyDismissed, setClarifyDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [repoRefreshKey, setRepoRefreshKey] = useState(0);
  const [payload, setPayload] = useState<V23RunPayload | null>(null);
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const streamRef = useRef<AbortController | null>(null);
  // Track the last run_id we surfaced to the parent so we don't fire
  // onRunIdChange on every render once the id stabilises.
  const lastEmittedRunIdRef = useRef<string | null>(null);

  // Reattach: when the page mounts (or navigates) with ?run_id_v23=<id>,
  // pull the persisted state so the user lands back on the report,
  // clarify modal, or error banner they left. Mid-RUNNING reattach is
  // handled by the polling effect below (no live SSE to re-subscribe to).
  useEffect(() => {
    if (!initialRunId) return;
    if (run?.run_id === initialRunId) return;
    let cancelled = false;
    setError(null);
    setFailedStage(null);
    getV23Run(initialRunId)
      .then((state) => {
        if (cancelled) return;
        setRun(state);
        setStage(state.current_stage);
        setSubmittedPrompt(state.raw_prompt);
        setSubmittedTickers(state.tickers);
        // Infer the completed-stage set from position in the linear
        // pipeline: anything before current_stage is treated as
        // complete. Retries can't be reconstructed from a persisted
        // snapshot — the chip shows retry_count only when the SSE
        // stream is live.
        setCompletedStages(stagesBefore(state.current_stage));
        if (state.status === "failed" && state.current_stage) {
          setFailedStage(state.current_stage);
        }
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : "failed to load run");
      });
    return () => {
      cancelled = true;
    };
  }, [initialRunId, run?.run_id]);

  // Surface the active run_id to the parent so it can persist it in the
  // URL. Fires on terminal SSE state, on reattach, and on reset.
  useEffect(() => {
    const next = run?.run_id ?? null;
    if (next === lastEmittedRunIdRef.current) return;
    lastEmittedRunIdRef.current = next;
    onRunIdChange?.(next);
  }, [run?.run_id, onRunIdChange]);

  // Auto-reopen the clarify modal whenever the run transitions back into
  // a fresh waiting_on_user phase (e.g. a new clarify round after the
  // user resumed). The dismissed flag is per-phase, not per-run.
  useEffect(() => {
    if (run?.status !== "waiting_on_user") {
      if (clarifyDismissed) setClarifyDismissed(false);
    }
  }, [run?.status, clarifyDismissed]);

  const parseTickers = (raw: string): string[] =>
    raw
      .split(/[,\s]+/)
      .map((t) => t.trim().toUpperCase())
      .filter(Boolean);

  const closeStream = useCallback(() => {
    if (streamRef.current !== null) {
      streamRef.current.abort();
      streamRef.current = null;
    }
  }, []);

  useEffect(() => () => closeStream(), [closeStream]);

  // Polling fallback: when a run is RUNNING but no live SSE stream is
  // attached (page reload mid-run, or SSE errored after we cached the
  // run_id), poll the run state until it leaves RUNNING. Each tick
  // also refreshes the inferred completed-stage set so the strip
  // advances as the engine progresses on the server.
  useEffect(() => {
    if (run?.status !== "running") return;
    if (busy) return; // a live SSE stream is in flight
    const runId = run.run_id;
    let cancelled = false;
    let timer: number | null = null;
    const tick = () => {
      if (cancelled) return;
      getV23Run(runId)
        .then((next) => {
          if (cancelled) return;
          setRun(next);
          if (next.current_stage !== null) {
            setStage(next.current_stage);
            setCompletedStages(stagesBefore(next.current_stage));
          }
          if (next.status === "running") {
            timer = window.setTimeout(tick, 1500);
          }
        })
        .catch(() => {
          if (cancelled) return;
          // Transient error — keep polling; surfacing a banner here would
          // flicker as the network recovers.
          timer = window.setTimeout(tick, 1500);
        });
    };
    timer = window.setTimeout(tick, 1500);
    return () => {
      cancelled = true;
      if (timer !== null) window.clearTimeout(timer);
    };
  }, [run?.run_id, run?.status, busy]);

  // Fetch the structured payload whenever a run reaches `complete`.
  useEffect(() => {
    if (run?.status !== "complete") return;
    let cancelled = false;
    setPayloadError(null);
    getV23RunPayload(run.run_id)
      .then((p) => {
        if (!cancelled) setPayload(p);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setPayloadError(e instanceof Error ? e.message : "failed to load report payload");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [run?.status, run?.run_id]);

  const handleStreamEvent = useCallback(
    (evt: import("../../api/equity-research-v2-3").V23StreamEvent) => {
      if (evt.event === "stage_started") {
        setStage(evt.data.slot);
      } else if (evt.event === "stage_completed") {
        const slot = evt.data.slot;
        setCompletedStages((prev) => {
          if (prev.has(slot)) return prev;
          const next = new Set(prev);
          next.add(slot);
          return next;
        });
      } else if (evt.event === "suspended") {
        setStage(evt.data.slot);
      } else if (evt.event === "failed") {
        setError(evt.data.error);
        if (evt.data.slot) setFailedStage(evt.data.slot);
        setBusy(false);
        setRepoRefreshKey((k) => k + 1);
      } else if (evt.event === "completed") {
        setStage(null);
      } else if (evt.event === "state") {
        setRun(evt.data);
        setBusy(false);
        setRepoRefreshKey((k) => k + 1);
      }
    },
    [],
  );

  const clarifyAssigned = Boolean(assignments?.assignments?.clarify);
  const totalSlots = assignments
    ? Object.keys(assignments.assignments).length
    : 0;
  const readyToRun = clarifyAssigned;

  const handleComposerSubmit = (payload: ComposerSubmitPayload) => {
    const parsed = parseTickers(payload.ticker);
    const promptText = payload.prompt.trim();
    if (parsed.length === 0 || !promptText) {
      setError("Provide at least one ticker and a prompt.");
      return;
    }
    setError(null);
    setBusy(true);
    setAnswers({});
    setRun(null);
    setStage(null);
    setCompletedStages(new Set());
    setFailedStage(null);
    setClarifyDismissed(false);
    setPayload(null);
    setPayloadError(null);
    setSubmittedPrompt(promptText);
    setSubmittedTickers(parsed);
    setPrompt("");
    closeStream();
    streamRef.current = streamV23Run(
      {
        raw_prompt: promptText,
        tickers: parsed,
        report_type: MODE_TO_V23_TYPE[mode],
      },
      {
        onEvent: handleStreamEvent,
        onError: (e) => {
          setError(e.message);
          setBusy(false);
        },
      },
    );
  };

  const submitAnswers = (override?: Record<string, string>) => {
    if (!run) return;
    setBusy(true);
    setError(null);
    closeStream();
    streamRef.current = streamV23Answer(run.run_id, override ?? answers, {
      onEvent: handleStreamEvent,
      onError: (e) => {
        setError(e.message);
        setBusy(false);
      },
    });
  };

  const needsClarify =
    run?.status === "waiting_on_user" && run.pending_questions.length > 0;

  const restart = useCallback(() => {
    closeStream();
    setRun(null);
    setStage(null);
    setCompletedStages(new Set());
    setFailedStage(null);
    setClarifyDismissed(false);
    setAnswers({});
    setPayload(null);
    setPayloadError(null);
    setError(null);
    setBusy(false);
    setSubmittedPrompt(null);
    setSubmittedTickers([]);
  }, [closeStream]);

  const isWelcome =
    run === null && !busy && payload === null && stage === null;
  const stop = useCallback(() => {
    closeStream();
    setBusy(false);
  }, [closeStream]);

  const placeholder = isWelcome
    ? "What should this report cover? (e.g., focus on AI infra margins)"
    : "Ask for another v2.3 report…";

  return (
    <div
      className="flex flex-1 min-h-0 flex-col"
      data-testid="er-v2-3-composer"
    >
      {/* Main scrollable area: WelcomeStage (welcome) or active content. */}
      <div className="flex flex-1 min-h-0 flex-col overflow-y-auto">
        {isWelcome ? (
          <>
            <WelcomeStage
              firstName={firstName}
              mode={mode}
              length={length}
              onModeRowClick={onModeClick}
            />
            <div className="mx-auto w-full max-w-[760px] px-4 pb-4">
              {!readyToRun && assignments !== null ? (
                <div className="mb-3">
                  <SetupBanner totalSlots={totalSlots} />
                </div>
              ) : null}
              <V23RepoPanel
                refreshKey={repoRefreshKey}
                onSelect={
                  onSelectPastRun
                    ? (summary) => onSelectPastRun(summary.run_id)
                    : undefined
                }
              />
            </div>
          </>
        ) : (
          <div className="mx-auto flex w-full max-w-[760px] flex-col gap-4 px-6 py-6">
            {submittedPrompt ? (
              <div className="flex flex-col items-end gap-1">
                <UserBubble
                  content={
                    submittedTickers.length > 0
                      ? `${submittedTickers.join(", ")} — ${submittedPrompt}`
                      : submittedPrompt
                  }
                />
              </div>
            ) : null}

            {run !== null || stage !== null ? (
              <V23StageStrip
                activeStage={
                  run?.status === "complete"
                    ? null
                    : (stage ?? run?.current_stage ?? null)
                }
                completed={completedStages}
                failedStage={failedStage}
                retryCount={run?.retry_count ?? 0}
                allComplete={run?.status === "complete"}
              />
            ) : null}

            {run !== null ? <V23RunBadge run={run} liveStage={stage} /> : null}

            {needsClarify && clarifyDismissed ? (
              <button
                type="button"
                onClick={() => setClarifyDismissed(false)}
                data-testid="er-v2-3-clarify-reopen"
                className="self-start inline-flex items-center gap-[6px] rounded-full border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] px-3 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-feedback-warning] hover:bg-[rgba(255,180,0,0.16)]"
              >
                <AlertTriangle size={11} /> Continue clarifying (
                {run.pending_questions.length})
              </button>
            ) : null}

            {run?.status === "failed" ? (
              <V23FailedReportCard
                runId={run.run_id}
                failedStage={failedStage ?? run.current_stage}
                lastError={run.last_error}
                retryCount={run.retry_count}
                onRestart={restart}
              />
            ) : null}

            {payload !== null ? (
              <V23ReportCard
                payload={payload}
                completedAt={
                  run?.status === "complete"
                    ? new Date().toISOString()
                    : null
                }
                onOpen={() => onOpenReport?.(payload.run_id)}
              />
            ) : null}
            {payloadError !== null ? (
              <div
                role="alert"
                className="rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
              >
                Could not load the report view: {payloadError}. The .docx
                download still works.
              </div>
            ) : null}
          </div>
        )}
      </div>

      {/* Inline error sits above the composer so it's visible on submit. */}
      {error ? (
        <div className="flex-shrink-0 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-6 pt-3">
          <div
            role="alert"
            data-testid="er-v2-3-error"
            className="mx-auto flex max-w-[760px] items-center gap-[8px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
          >
            <AlertTriangle size={13} /> {error}
          </div>
        </div>
      ) : null}

      {/* Bottom-pinned ErComposer — the same composer v2.2 uses, so v2.3
       *  shares the welcome/composer chrome pixel-for-pixel. */}
      <ErComposer
        value={prompt}
        onChange={setPrompt}
        onSubmit={handleComposerSubmit}
        onStop={stop}
        isStreaming={busy}
        placeholder={placeholder}
        mode={mode}
        length={length}
        onModeClick={onModeClick}
        disabled={!readyToRun}
        ticker={isWelcome ? tickerInput : undefined}
        onTickerChange={isWelcome ? setTickerInput : undefined}
      />

      {/* Clarify modal — overlay above everything else. */}
      {needsClarify && !clarifyDismissed ? (
        <V23ClarifyModal
          questions={run.pending_questions}
          answers={answers}
          busy={busy}
          onChange={setAnswers}
          onSubmit={() => submitAnswers()}
          onUseDefaults={() => submitAnswers({})}
          onDismiss={() => setClarifyDismissed(true)}
        />
      ) : null}
    </div>
  );
}

function SetupBanner({ totalSlots }: { totalSlots: number }): JSX.Element {
  return (
    <div
      role="status"
      data-testid="er-v2-3-setup-banner"
      className="flex items-start gap-[10px] rounded-md border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] px-3 py-2 text-[12px] text-[--color-text-primary]"
    >
      <AlertTriangle
        size={13}
        className="mt-[2px] text-[--color-feedback-warning]"
      />
      <div className="flex flex-1 flex-col gap-[2px]">
        <span className="font-medium">
          Configure engine models before running a v2.3 report.
        </span>
        <span className="text-[--color-text-secondary]">
          Assign at least the <strong>Clarify</strong> slot ({totalSlots}/7
          assigned). Open <em>Engine models</em> in the page header.
        </span>
      </div>
    </div>
  );
}

function stagesBefore(current: V23Stage | null): Set<V23Stage> {
  if (current === null) return new Set();
  const idx = STAGE_ORDER.indexOf(current);
  if (idx <= 0) return new Set();
  return new Set(STAGE_ORDER.slice(0, idx));
}

function V23RunBadge({
  run,
  liveStage,
}: {
  run: V23RunState;
  liveStage: V23Stage | null;
}): JSX.Element {
  const activeStage = liveStage ?? run.current_stage;
  const stageLabel = activeStage !== null ? STAGE_LABEL[activeStage] : "Idle";
  const statusColor =
    run.status === "failed"
      ? "text-[--color-feedback-danger]"
      : run.status === "complete"
        ? "text-[--color-feedback-success]"
        : "text-[--color-text-secondary]";
  return (
    <div
      data-testid="er-v2-3-run-status"
      className="flex items-center justify-between gap-[10px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 font-mono text-[11px] uppercase tracking-[0.08em]"
    >
      <span className="text-[--color-text-tertiary]">{run.run_id.slice(0, 12)}…</span>
      <span className={`flex items-center gap-[8px] ${statusColor}`}>
        <span>
          {run.status} · {stageLabel}
          {run.retry_count > 0 ? ` · retry ${run.retry_count}` : ""}
        </span>
        {run.status === "complete" ? (
          <a
            href={v23DocxUrl(run.run_id)}
            download
            data-testid="er-v2-3-download"
            className="inline-flex items-center gap-[4px] rounded-md border border-[--color-feedback-success] bg-[--color-bg-elevated] px-2 py-[2px] text-[--color-feedback-success] hover:bg-[rgba(80,180,80,0.10)]"
          >
            <Download size={11} /> .docx
          </a>
        ) : null}
      </span>
    </div>
  );
}

