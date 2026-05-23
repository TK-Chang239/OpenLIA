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
import { AlertTriangle, Download, Loader2, Send } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import type { AssignmentsResponse } from "../../api/er-v2-3-models";
import {
  type V23ClarifyQuestion,
  type V23ReportType,
  type V23RunPayload,
  type V23RunState,
  type V23Stage,
  getV23RunPayload,
  streamV23Answer,
  streamV23Run,
  v23DocxUrl,
} from "../../api/equity-research-v2-3";
import { V23EngineModelsPicker } from "./V23EngineModelsPicker";
import { V23RepoPanel } from "./V23RepoPanel";
import { V23ReportView } from "./V23ReportView";

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

export function V23Composer(): JSX.Element {
  const [prompt, setPrompt] = useState("");
  const [tickers, setTickers] = useState("");
  const [reportType, setReportType] = useState<V23ReportType>("initiation");
  const [run, setRun] = useState<V23RunState | null>(null);
  const [stage, setStage] = useState<V23Stage | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [assignments, setAssignments] = useState<AssignmentsResponse | null>(null);
  const [repoRefreshKey, setRepoRefreshKey] = useState(0);
  const [payload, setPayload] = useState<V23RunPayload | null>(null);
  const [payloadError, setPayloadError] = useState<string | null>(null);
  const streamRef = useRef<AbortController | null>(null);

  const parsedTickers = tickers
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
        // No-op: stage_started already reflects the active stage.
      } else if (evt.event === "suspended") {
        setStage(evt.data.slot);
      } else if (evt.event === "failed") {
        setError(evt.data.error);
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

  const send = () => {
    if (parsedTickers.length === 0 || !prompt.trim()) {
      setError("Provide at least one ticker and a prompt.");
      return;
    }
    setError(null);
    setBusy(true);
    setAnswers({});
    setPayload(null);
    setPayloadError(null);
    closeStream();
    streamRef.current = streamV23Run(
      {
        raw_prompt: prompt,
        tickers: parsedTickers,
        report_type: reportType,
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

  const submitAnswers = () => {
    if (!run) return;
    setBusy(true);
    setError(null);
    closeStream();
    streamRef.current = streamV23Answer(run.run_id, answers, {
      onEvent: handleStreamEvent,
      onError: (e) => {
        setError(e.message);
        setBusy(false);
      },
    });
  };

  const needsClarify =
    run?.status === "waiting_on_user" && run.pending_questions.length > 0;

  return (
    <div className="flex flex-col gap-[14px]" data-testid="er-v2-3-composer">
      <div className="flex items-center justify-between gap-[10px]">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          Equity Research v2.3 (preview)
        </span>
        <V23EngineModelsPicker onAssignmentsChange={setAssignments} />
      </div>

      {!readyToRun && assignments !== null ? (
        <div
          role="status"
          data-testid="er-v2-3-setup-banner"
          className="flex items-start gap-[10px] rounded-md border border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] px-3 py-2 text-[12px] text-[--color-text-primary]"
        >
          <AlertTriangle size={13} className="mt-[2px] text-[--color-feedback-warning]" />
          <div className="flex flex-1 flex-col gap-[2px]">
            <span className="font-medium">
              Configure engine models before running a v2.3 report.
            </span>
            <span className="text-[--color-text-secondary]">
              At minimum, assign a model to the <strong>Clarify</strong> slot
              ({totalSlots}/7 assigned). Open <em>Engine models</em> above, or
              visit Settings → Models to enable a provider/model first.
            </span>
          </div>
        </div>
      ) : null}

      <V23RepoPanel refreshKey={repoRefreshKey} />


      <input
        type="text"
        value={tickers}
        onChange={(e) => setTickers(e.target.value)}
        placeholder="Tickers (NVDA, AVGO, …)"
        className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[12px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
        data-testid="er-v2-3-tickers"
      />

      <select
        value={reportType}
        onChange={(e) => setReportType(e.target.value as V23ReportType)}
        className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[12px] text-[--color-text-primary]"
        data-testid="er-v2-3-report-type"
      >
        <option value="initiation">Initiation</option>
        <option value="update">Update</option>
        <option value="morning_brief">Morning brief</option>
        <option value="earnings_review">Earnings review</option>
      </select>

      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        placeholder="What should the report cover?"
        rows={4}
        className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
        data-testid="er-v2-3-prompt"
      />

      <div className="flex items-center justify-end">
        <button
          type="button"
          onClick={send}
          disabled={busy || !readyToRun}
          title={
            !readyToRun
              ? "Assign at least the Clarify model in Engine models first"
              : ""
          }
          data-testid="er-v2-3-send"
          className="inline-flex h-9 items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Send size={13} />
          )}
          {busy ? "Working..." : "Run"}
        </button>
      </div>

      {error ? (
        <div
          role="alert"
          className="flex items-center gap-[8px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
        >
          <AlertTriangle size={13} /> {error}
        </div>
      ) : null}

      {run ? <V23RunBadge run={run} liveStage={stage} /> : null}
      {!run && stage !== null ? (
        <div
          data-testid="er-v2-3-live-stage"
          className="flex items-center justify-end rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary]"
        >
          {STAGE_LABEL[stage]}…
        </div>
      ) : null}

      {needsClarify ? (
        <ClarifyForm
          questions={run.pending_questions}
          answers={answers}
          onChange={setAnswers}
          onSubmit={submitAnswers}
          busy={busy}
        />
      ) : null}

      {payload !== null ? <V23ReportView payload={payload} /> : null}
      {payloadError !== null ? (
        <div
          role="alert"
          className="rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
        >
          Could not load the report view: {payloadError}. The .docx download still works.
        </div>
      ) : null}
    </div>
  );
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

function ClarifyForm({
  questions,
  answers,
  onChange,
  onSubmit,
  busy,
}: {
  questions: V23ClarifyQuestion[];
  answers: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
  onSubmit: () => void;
  busy: boolean;
}): JSX.Element {
  return (
    <div
      data-testid="er-v2-3-clarify"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-3"
    >
      <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        Clarify · {questions.length} question(s)
      </div>
      <ul className="flex flex-col gap-2">
        {questions.map((q) => (
          <li key={q.id} className="flex flex-col gap-[4px]">
            <label className="text-[12.5px] text-[--color-text-primary]" htmlFor={`q-${q.id}`}>
              {q.question}
            </label>
            <span className="text-[11px] text-[--color-text-tertiary]">
              {q.why_blocking} · default: {q.default}
            </span>
            <input
              id={`q-${q.id}`}
              type="text"
              value={answers[q.id] ?? ""}
              onChange={(e) => onChange({ ...answers, [q.id]: e.target.value })}
              placeholder={q.default}
              className="h-8 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-2 font-mono text-[11.5px] text-[--color-text-primary]"
              data-testid={`er-v2-3-clarify-${q.id}`}
            />
          </li>
        ))}
      </ul>
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={onSubmit}
          disabled={busy}
          data-testid="er-v2-3-clarify-submit"
          className="inline-flex h-8 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[12.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Sending..." : "Continue"}
        </button>
      </div>
    </div>
  );
}
