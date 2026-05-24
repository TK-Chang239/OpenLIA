/**
 * V23StageStrip — horizontal progress strip for the v2.3 pipeline.
 *
 * Renders the eight stages of the v2.3 subagent pipeline as a row of
 * dots with labels and connector lines. Each stage shows one of:
 *
 *   pending  -> outline dot, muted label
 *   active   -> filled accent dot with pulse animation
 *   complete -> filled success dot with check icon
 *   failed   -> filled danger dot with x icon
 *
 * Stages are listed in execution order; the deterministic ASSEMBLE
 * stage is intentionally omitted because the engine doesn't emit
 * stage_started / stage_completed for it — once VERIFY passes, the
 * run flips straight to ``complete`` with the resolved report ready.
 */
import { Check, X } from "lucide-react";
import { Fragment, type JSX } from "react";

import type { V23Stage } from "../../api/equity-research-v2-3";

interface StageDef {
  slot: V23Stage;
  label: string;
}

const STAGES: readonly StageDef[] = [
  { slot: "clarify", label: "Clarify" },
  { slot: "plan", label: "Plan" },
  { slot: "research", label: "Research" },
  { slot: "compute", label: "Compute" },
  { slot: "synthesize", label: "Synthesize" },
  { slot: "write", label: "Write" },
  { slot: "visualize", label: "Visualize" },
  { slot: "verify", label: "Verify" },
];

type StageState = "pending" | "active" | "complete" | "failed";

interface Props {
  /** Stage currently executing, or null when idle / complete. */
  activeStage: V23Stage | null;
  /** Stages the run has already finished. */
  completed: ReadonlySet<V23Stage>;
  /** Stage that raised the terminal failure, when status is FAILED. */
  failedStage?: V23Stage | null;
  /** Engine-reported retry count on the active stage. */
  retryCount?: number;
  /** When true, paint every stage as complete (run finished). */
  allComplete?: boolean;
}

export function V23StageStrip({
  activeStage,
  completed,
  failedStage = null,
  retryCount = 0,
  allComplete = false,
}: Props): JSX.Element {
  return (
    <div
      data-testid="er-v2-3-stage-strip"
      className="flex items-start gap-1 overflow-x-auto rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-3"
    >
      {STAGES.map((stage, i) => {
        const state: StageState = allComplete
          ? "complete"
          : failedStage === stage.slot
            ? "failed"
            : activeStage === stage.slot
              ? "active"
              : completed.has(stage.slot)
                ? "complete"
                : "pending";
        const showRetry = state === "active" && retryCount > 0;
        return (
          <Fragment key={stage.slot}>
            {i > 0 ? <Connector left={STAGES[i - 1].slot} right={stage.slot} completed={completed} allComplete={allComplete} /> : null}
            <StageChip
              slot={stage.slot}
              label={stage.label}
              state={state}
              retryCount={showRetry ? retryCount : 0}
            />
          </Fragment>
        );
      })}
    </div>
  );
}

function StageChip({
  slot,
  label,
  state,
  retryCount,
}: {
  slot: V23Stage;
  label: string;
  state: StageState;
  retryCount: number;
}): JSX.Element {
  const dotClass =
    state === "active"
      ? "bg-[--color-accent-primary] animate-pulse"
      : state === "complete"
        ? "bg-[--color-feedback-success] text-white"
        : state === "failed"
          ? "bg-[--color-feedback-danger] text-white"
          : "border border-[--color-border-strong] bg-transparent";
  const labelClass =
    state === "active"
      ? "text-[--color-text-primary]"
      : state === "failed"
        ? "text-[--color-feedback-danger]"
        : "text-[--color-text-tertiary]";
  return (
    <div
      className="flex min-w-[58px] flex-col items-center gap-1"
      data-testid={`er-v2-3-stage-${slot}`}
      data-state={state}
    >
      <span
        className={`flex h-3.5 w-3.5 items-center justify-center rounded-full ${dotClass}`}
        aria-hidden="true"
      >
        {state === "complete" ? <Check size={9} strokeWidth={3} /> : null}
        {state === "failed" ? <X size={9} strokeWidth={3} /> : null}
      </span>
      <span
        className={`font-mono text-[9px] uppercase tracking-[0.08em] ${labelClass}`}
      >
        {label}
      </span>
      {retryCount > 0 ? (
        <span
          className="font-mono text-[8.5px] uppercase tracking-[0.08em] text-[--color-feedback-warning]"
          data-testid={`er-v2-3-stage-${slot}-retry`}
        >
          retry {retryCount}
        </span>
      ) : null}
    </div>
  );
}

function Connector({
  left,
  right,
  completed,
  allComplete,
}: {
  left: V23Stage;
  right: V23Stage;
  completed: ReadonlySet<V23Stage>;
  allComplete: boolean;
}): JSX.Element {
  const lit = allComplete || (completed.has(left) && completed.has(right));
  const color = lit ? "bg-[--color-feedback-success]" : "bg-[--color-border-subtle]";
  return (
    <span
      aria-hidden="true"
      className={`mt-[6px] h-px min-w-[14px] flex-1 ${color}`}
    />
  );
}
