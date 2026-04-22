import { useEffect, useMemo, useState } from "react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { finish, pollReview, runReview } from "../../api/setup";
import type { Mode, ReviewPoll } from "../../api/setup";

interface ReviewResult {
  summary: string;
  departments: {
    id: string;
    state: "ready" | "gaps" | "disabled" | "blocked";
    note: string | null;
    basic: { type: string; provider: string | null; confidence: number }[];
    advanced: { type: string; provider: string | null; confidence: number }[];
    unmet: string[];
  }[];
}

export function ReviewStep({
  totalSteps,
  mode,
  onBack,
}: {
  totalSteps: number;
  mode: Mode;
  onBack: () => void;
}) {
  const [state, setState] = useState<"starting" | "running" | "complete" | "failed">("starting");
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [finishing, setFinishing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;
    (async () => {
      try {
        setState("running");
        const { review_id } = await runReview();
        const loop = async () => {
          if (cancelled) return;
          const poll: ReviewPoll = await pollReview(review_id);
          if (poll.state === "complete") {
            setResult(poll.result as ReviewResult);
            setState("complete");
          } else if (poll.state === "failed") {
            setError(poll.error ?? "Review failed.");
            setState("failed");
          } else {
            timer = setTimeout(loop, 1500);
          }
        };
        await loop();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to start review.");
        setState("failed");
      }
    })();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const blocked = useMemo(
    () => result?.departments.some((d) => d.state === "blocked") ?? false,
    [result],
  );

  const onFinish = async () => {
    setFinishing(true);
    try {
      const { redirect } = await finish();
      window.location.href = redirect;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to finish.");
    } finally {
      setFinishing(false);
    }
  };

  return (
    <WizardShell
      title="Review"
      stepIndex={totalSteps - 1}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onFinish}
          nextLabel="Finish"
          nextDisabled={state !== "complete" || blocked}
          loading={finishing}
        />
      }
    >
      {state === "running" ? (
        <p className="text-sm text-[--color-text-secondary]">
          Mapping providers to department requirements…
        </p>
      ) : null}
      {state === "failed" ? (
        <p className="text-sm text-[--color-feedback-error]">{error}</p>
      ) : null}
      {state === "complete" && result ? (
        <>
          <p className="text-sm text-[--color-text-primary] font-medium mb-4">{result.summary}</p>
          <div className="grid grid-cols-2 gap-3">
            {result.departments.map((d) => (
              <article
                key={d.id}
                className="border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-elevated] p-4 flex justify-between gap-3"
                style={{
                  borderLeftWidth: 3,
                  borderLeftColor:
                    d.state === "ready"
                      ? "var(--color-feedback-success)"
                      : d.state === "gaps"
                        ? "var(--color-feedback-warning)"
                        : d.state === "blocked"
                          ? "var(--color-feedback-error)"
                          : "var(--color-border-subtle)",
                }}
              >
                <div>
                  <h4 className="text-sm font-semibold text-[--color-text-primary] capitalize">
                    {d.id.replace("_", " ")}
                  </h4>
                  {d.unmet.length > 0 ? (
                    <p className="text-xs text-[--color-text-secondary] mt-1 leading-relaxed">
                      Unmet: {d.unmet.join(", ")}
                    </p>
                  ) : null}
                </div>
                <span
                  aria-label={`${d.id} ${d.state}`}
                  className={`text-xs px-2 py-0.5 rounded-full h-fit ${
                    d.state === "ready"
                      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
                      : d.state === "gaps"
                        ? "bg-[--color-feedback-warning]/15 text-[--color-feedback-warning]"
                        : d.state === "blocked"
                          ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
                          : "bg-[--color-surface-active] text-[--color-text-tertiary]"
                  }`}
                >
                  {d.state}
                </span>
              </article>
            ))}
          </div>
          {blocked ? (
            <p className="text-sm text-[--color-feedback-error] mt-4">
              Go back to Data Providers to cover the unmet requirements.
            </p>
          ) : null}
        </>
      ) : null}
    </WizardShell>
  );
}
