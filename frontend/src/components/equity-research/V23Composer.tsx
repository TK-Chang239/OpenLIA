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
import { AlertTriangle, Loader2, Send } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import {
  type V23ClarifyQuestion,
  type V23ReportType,
  type V23RunState,
  type V23Stage,
  answerV23Run,
  getV23Run,
  startV23Run,
} from "../../api/equity-research-v2-3";
import { V23EngineModelsPicker } from "./V23EngineModelsPicker";

const POLL_INTERVAL_MS = 1500;
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
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const parsedTickers = tickers
    .split(/[,\s]+/)
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const scheduleNextPoll = useCallback(
    (state: V23RunState) => {
      stopPolling();
      if (state.status !== "running") return;
      pollRef.current = setTimeout(async () => {
        try {
          const next = await getV23Run(state.run_id);
          setRun(next);
          scheduleNextPoll(next);
        } catch (e) {
          setError(e instanceof Error ? e.message : "poll failed");
        }
      }, POLL_INTERVAL_MS);
    },
    [stopPolling],
  );

  const send = async () => {
    if (parsedTickers.length === 0 || !prompt.trim()) {
      setError("Provide at least one ticker and a prompt.");
      return;
    }
    setError(null);
    setBusy(true);
    setAnswers({});
    try {
      const next = await startV23Run({
        raw_prompt: prompt,
        tickers: parsedTickers,
        report_type: reportType,
      });
      setRun(next);
      scheduleNextPoll(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to start run");
    } finally {
      setBusy(false);
    }
  };

  const submitAnswers = async () => {
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      const next = await answerV23Run(run.run_id, answers);
      setRun(next);
      scheduleNextPoll(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to submit answers");
    } finally {
      setBusy(false);
    }
  };

  const needsClarify =
    run?.status === "waiting_on_user" && run.pending_questions.length > 0;

  return (
    <div className="flex flex-col gap-[14px]" data-testid="er-v2-3-composer">
      <div className="flex items-center justify-between gap-[10px]">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          Equity Research v2.3 (preview)
        </span>
        <V23EngineModelsPicker />
      </div>

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
          disabled={busy}
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

      {run ? <V23RunBadge run={run} /> : null}

      {needsClarify ? (
        <ClarifyForm
          questions={run.pending_questions}
          answers={answers}
          onChange={setAnswers}
          onSubmit={submitAnswers}
          busy={busy}
        />
      ) : null}
    </div>
  );
}

function V23RunBadge({ run }: { run: V23RunState }): JSX.Element {
  const stageLabel =
    run.current_stage !== null ? STAGE_LABEL[run.current_stage] : "Idle";
  const statusColor =
    run.status === "failed"
      ? "text-[--color-feedback-danger]"
      : run.status === "complete"
        ? "text-[--color-feedback-success]"
        : "text-[--color-text-secondary]";
  return (
    <div
      data-testid="er-v2-3-run-status"
      className="flex items-center justify-between rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 font-mono text-[11px] uppercase tracking-[0.08em]"
    >
      <span className="text-[--color-text-tertiary]">{run.run_id.slice(0, 12)}…</span>
      <span className={statusColor}>
        {run.status} · {stageLabel}
        {run.retry_count > 0 ? ` · retry ${run.retry_count}` : ""}
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
