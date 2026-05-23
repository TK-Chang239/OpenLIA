/**
 * V23FailedReportCard — terminal-failure display for a v2.3 run.
 *
 * Surfaces the engine-reported error and the slot it failed in,
 * with a Restart button that clears local state so the user can
 * recompose. v2.3 doesn't yet expose resume-from-stage, so restart
 * is the only path forward; the spec calls this out explicitly.
 */
import { AlertOctagon, RotateCcw } from "lucide-react";
import { type JSX } from "react";

import type { V23Stage } from "../../api/equity-research-v2-3";

const STAGE_LABEL: Record<V23Stage, string> = {
  clarify: "Clarify",
  plan: "Plan",
  research: "Research",
  compute: "Compute",
  synthesize: "Synthesize",
  write: "Write",
  visualize: "Visualize",
  verify: "Verify",
};

interface Props {
  runId: string;
  failedStage: V23Stage | null;
  /** engine-reported error message; nullable because some failures
   *  arrive via SSE before the persisted run state catches up */
  lastError: string | null;
  retryCount: number;
  onRestart: () => void;
}

export function V23FailedReportCard({
  runId,
  failedStage,
  lastError,
  retryCount,
  onRestart,
}: Props): JSX.Element {
  const stageLabel = failedStage ? STAGE_LABEL[failedStage] : "Pipeline";
  return (
    <article
      data-testid="er-v2-3-failed-card"
      className="overflow-hidden rounded-lg border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.06)] shadow-sm"
    >
      <header className="flex items-start gap-3 px-4 py-3">
        <AlertOctagon
          size={16}
          className="mt-[2px] flex-shrink-0 text-[--color-feedback-danger]"
        />
        <div className="flex flex-1 flex-col gap-[2px]">
          <div className="font-display text-[14px] font-medium text-[--color-feedback-danger]">
            Run failed during {stageLabel}
          </div>
          <div className="font-mono text-[10.5px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {runId.slice(0, 12)}…
            {retryCount > 0 ? ` · ${retryCount} retry attempt${retryCount === 1 ? "" : "s"}` : ""}
          </div>
        </div>
      </header>

      <div
        data-testid="er-v2-3-failed-card-error"
        className="border-t border-[rgba(220,80,80,0.25)] px-4 py-3 font-mono text-[11.5px] leading-[1.55] text-[--color-text-primary]"
      >
        {lastError && lastError.trim().length > 0
          ? lastError
          : "The engine raised an unspecified failure. The persisted run state has details."}
      </div>

      <footer className="flex items-center justify-between gap-2 border-t border-[rgba(220,80,80,0.25)] bg-[--color-bg-base] px-4 py-2.5">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          v2.3 has no mid-stage resume — restart from the prompt to recover.
        </span>
        <button
          type="button"
          onClick={onRestart}
          data-testid="er-v2-3-failed-card-restart"
          className="inline-flex h-7 items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 font-display text-[12.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
        >
          <RotateCcw size={12} /> Restart
        </button>
      </footer>
    </article>
  );
}
