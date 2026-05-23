/**
 * V23ClarifyModal — top-level overlay for the v2.3 CLARIFY stage.
 *
 * The v2.3 engine can suspend a run with `RunStatus.waiting_on_user`
 * and a list of `pending_questions`. This modal collects answers and
 * lets the user resume or fall back to the engine-provided defaults.
 * Backdrop click and Esc dismiss without cancelling the run — the
 * caller is expected to surface a "Continue clarifying" pill so the
 * user can reopen.
 */
import { type JSX, useCallback, useEffect } from "react";

import type { V23ClarifyQuestion } from "../../api/equity-research-v2-3";

interface Props {
  questions: V23ClarifyQuestion[];
  answers: Record<string, string>;
  busy: boolean;
  onChange: (next: Record<string, string>) => void;
  /** Submit the collected answers. Empty values fall back to each
   *  question's `default` server-side. */
  onSubmit: () => void;
  /** Submit an empty answers map so the engine uses every default. */
  onUseDefaults: () => void;
  /** Close the modal without cancelling the run. */
  onDismiss: () => void;
}

export function V23ClarifyModal({
  questions,
  answers,
  busy,
  onChange,
  onSubmit,
  onUseDefaults,
  onDismiss,
}: Props): JSX.Element {
  const dismiss = useCallback(() => {
    if (busy) return;
    onDismiss();
  }, [busy, onDismiss]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dismiss]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="er-v2-3-clarify-modal-title"
      data-testid="er-v2-3-clarify-modal"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        data-testid="er-v2-3-clarify-modal-backdrop"
        className="absolute inset-0 bg-black/40"
        onClick={dismiss}
      />
      <div className="relative z-10 mx-4 flex w-full max-w-[520px] flex-col gap-3 rounded-lg border border-[--color-border-subtle] bg-[--color-bg-elevated] px-5 py-4 shadow-lg">
        <header className="flex items-baseline justify-between gap-3">
          <h2
            id="er-v2-3-clarify-modal-title"
            className="font-display text-[15.5px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            Quick check before I start
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
            {questions.length} question{questions.length === 1 ? "" : "s"}
          </span>
        </header>
        <p className="text-[12.5px] text-[--color-text-secondary]">
          A couple of things to confirm so the report doesn't go sideways.
        </p>

        <ul className="flex flex-col gap-3">
          {questions.map((q) => (
            <li key={q.id} className="flex flex-col gap-[4px]">
              <label
                htmlFor={`er-v2-3-clarify-modal-${q.id}`}
                className="text-[13px] text-[--color-text-primary]"
              >
                {q.question}
              </label>
              <span className="text-[11.5px] text-[--color-text-tertiary]">
                {q.why_blocking} · default: {q.default}
              </span>
              <input
                id={`er-v2-3-clarify-modal-${q.id}`}
                type="text"
                value={answers[q.id] ?? ""}
                onChange={(e) =>
                  onChange({ ...answers, [q.id]: e.target.value })
                }
                placeholder={q.default}
                data-testid={`er-v2-3-clarify-modal-${q.id}`}
                className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[12px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
              />
            </li>
          ))}
        </ul>

        <footer className="mt-1 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onUseDefaults}
            disabled={busy}
            data-testid="er-v2-3-clarify-modal-defaults"
            className="inline-flex h-8 items-center rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Use defaults
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={dismiss}
              disabled={busy}
              data-testid="er-v2-3-clarify-modal-cancel"
              className="inline-flex h-8 items-center rounded-md px-3 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSubmit}
              disabled={busy}
              data-testid="er-v2-3-clarify-modal-submit"
              className="inline-flex h-8 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[12.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy ? "Sending…" : "Continue"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
