import type { ReactNode } from "react";
import type {
  DashboardResult,
  DashboardTier,
} from "../../../api/macro_research";

const SEVERITY_STYLES: Record<string, string> = {
  green: "bg-[--color-feedback-success] text-white",
  amber: "bg-[--color-feedback-warning] text-black",
  red: "bg-[--color-feedback-error] text-white",
  neutral: "bg-[--color-bg-elevated] text-[--color-text-primary]",
};

export function tierOf(
  result: DashboardResult | null,
  tier: DashboardTier["tier"],
): DashboardTier | undefined {
  return result?.tiers.find((t) => t.tier === tier);
}

export function SeverityPill({
  severity,
}: {
  severity: string;
}): JSX.Element {
  const cls = SEVERITY_STYLES[severity] ?? SEVERITY_STYLES.neutral;
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide ${cls}`}
      data-testid="severity-pill"
    >
      {severity}
    </span>
  );
}

export function SmartModeToggle({
  value,
  onChange,
}: {
  value: boolean;
  onChange: (next: boolean) => void;
}): JSX.Element {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-[--color-text-secondary]">
      <input
        role="switch"
        type="checkbox"
        aria-label="Smart Mode"
        checked={value}
        onChange={(e) => onChange(e.target.checked)}
        className="h-4 w-4"
      />
      Smart Mode
    </label>
  );
}

export function AssessmentBlock({
  text,
  generatedAt,
}: {
  text: string | null;
  generatedAt: string | null;
}): JSX.Element {
  return (
    <div className="rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4">
      <div className="flex items-baseline justify-between">
        <div className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
          Assessment
        </div>
        {generatedAt ? (
          <div className="text-xs text-[--color-text-tertiary]">
            {new Date(generatedAt).toLocaleString()}
          </div>
        ) : null}
      </div>
      <div className="mt-2 whitespace-pre-wrap text-sm text-[--color-text-primary]">
        {text ?? "No assessment cached yet. Run an assessment to generate one."}
      </div>
    </div>
  );
}

export function Panel({
  title,
  children,
  testid,
}: {
  title: string;
  children: ReactNode;
  testid?: string;
}): JSX.Element {
  return (
    <div
      data-testid={testid}
      className="rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4"
    >
      <div className="mb-2 text-xs uppercase tracking-wide text-[--color-text-tertiary]">
        {title}
      </div>
      {children}
    </div>
  );
}

export function LoadingBlock({ label }: { label: string }): JSX.Element {
  return (
    <div
      className="animate-pulse text-sm text-[--color-text-secondary]"
      role="status"
    >
      Loading {label}…
    </div>
  );
}

export function ErrorBlock({ message }: { message: string }): JSX.Element {
  return (
    <div
      role="alert"
      className="rounded-[--radius-md] border border-[--color-feedback-error] bg-[--color-bg-elevated] p-3 text-sm text-[--color-feedback-error]"
    >
      {message}
    </div>
  );
}
