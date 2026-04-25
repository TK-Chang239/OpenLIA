import type { ReactNode } from "react";
import { WizardProgress } from "./WizardProgress";

interface Props {
  title: string;
  stepIndex: number;
  totalSteps: number;
  children: ReactNode;
  footer?: ReactNode;
}

export function WizardShell({ title, stepIndex, totalSteps, children, footer }: Props) {
  const titleId = "wizard-title";
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-label={title}
      className="fixed inset-0 bg-bg-base overflow-auto"
    >
      <div className="max-w-[880px] w-[90%] mx-auto my-10 bg-bg-elevated rounded-lg shadow-md border border-border-subtle">
        <header className="h-14 flex items-center justify-between px-6 border-b border-border-subtle">
          <div className="flex flex-col gap-0.5">
            <span className="ol-label-sm">
              {`STEP ${(stepIndex + 1).toString().padStart(2, "0")} / ${totalSteps
                .toString()
                .padStart(2, "0")}`}
            </span>
            <h1 id={titleId} className="text-lg font-semibold text-text-primary">
              {title}
            </h1>
          </div>
          <span className="text-xs text-text-secondary">
            Step {stepIndex + 1} of {totalSteps}
          </span>
        </header>
        <WizardProgress value={stepIndex} max={totalSteps} />
        <div className="px-8 py-6">
          <div className="max-w-[640px] mx-auto">{children}</div>
        </div>
        {footer}
      </div>
    </div>
  );
}
