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
      className="fixed inset-0 bg-[--color-bg-base] overflow-auto"
    >
      <div className="max-w-[880px] w-[90%] mx-auto my-10 bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-md border border-[--color-border-subtle]">
        <header className="h-14 flex items-center justify-between px-6 border-b border-[--color-border-subtle]">
          <h1 id={titleId} className="text-lg font-semibold text-[--color-text-primary]">
            {title}
          </h1>
          <span className="text-xs text-[--color-text-secondary]">
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
