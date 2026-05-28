/**
 * V3ReportSettingsModal — minimal "Report Settings" modal for v3.
 *
 * v3 has no per-stage model assignments and no user-uploaded templates
 * yet, so this modal is intentionally smaller than V23: just the three
 * dials the v3 start payload exposes — report type, length, language.
 * The selection state is owned by the page; this component is purely
 * presentational.
 */
import { Check, X } from "lucide-react";
import { type JSX, useEffect } from "react";

import type {
  V3Language,
  V3ReportLength,
  V3ReportType,
} from "../../api/equity-research-v3";

const REPORT_TYPES: { value: V3ReportType; label: string; hint: string }[] = [
  {
    value: "initiation",
    label: "Stock Initiation",
    hint: "First-time deep dive on a company",
  },
  {
    value: "update",
    label: "Stock Update",
    hint: "Refresh on a previously-covered name",
  },
  {
    value: "sector_research",
    label: "Sector Research",
    hint: "Cross-company industry analysis",
  },
];

const LENGTHS: { value: V3ReportLength; label: string; hint: string }[] = [
  { value: "concise", label: "Concise", hint: "Tighter sections, fewer charts" },
  { value: "normal", label: "Normal", hint: "Balanced depth (default)" },
  { value: "elaborative", label: "Elaborative", hint: "Maximum detail" },
];

const LANGUAGES: { value: V3Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "zh-TW", label: "繁體中文" },
];

export interface V3ReportSettingsModalProps {
  open: boolean;
  reportType: V3ReportType;
  length: V3ReportLength;
  language: V3Language;
  onReportTypeChange: (next: V3ReportType) => void;
  onLengthChange: (next: V3ReportLength) => void;
  onLanguageChange: (next: V3Language) => void;
  onClose: () => void;
}

export function V3ReportSettingsModal({
  open,
  reportType,
  length,
  language,
  onReportTypeChange,
  onLengthChange,
  onLanguageChange,
  onClose,
}: V3ReportSettingsModalProps): JSX.Element | null {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="er-v3-settings-title"
      data-testid="er-v3-settings-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={onClose}
    >
      <div
        className="flex max-h-[86vh] w-full max-w-[560px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-[10px] border-b border-[--color-border-subtle] px-[22px] py-[16px]">
          <div className="flex min-w-0 flex-1 flex-col">
            <h2
              id="er-v3-settings-title"
              className="m-0 truncate text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
            >
              Report settings
            </h2>
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              v3 engine
            </span>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="flex-1 overflow-auto px-[22px] py-[16px]">
          <Section title="Report type">
            <div className="flex flex-col gap-[6px]">
              {REPORT_TYPES.map((opt) => (
                <RadioRow
                  key={opt.value}
                  active={reportType === opt.value}
                  label={opt.label}
                  hint={opt.hint}
                  onSelect={() => onReportTypeChange(opt.value)}
                  testId={`er-v3-report-type-${opt.value}`}
                />
              ))}
            </div>
          </Section>

          <Section title="Length">
            <div className="flex flex-col gap-[6px]">
              {LENGTHS.map((opt) => (
                <RadioRow
                  key={opt.value}
                  active={length === opt.value}
                  label={opt.label}
                  hint={opt.hint}
                  onSelect={() => onLengthChange(opt.value)}
                  testId={`er-v3-length-${opt.value}`}
                />
              ))}
            </div>
          </Section>

          <Section title="Language">
            <div className="flex flex-wrap gap-[6px]">
              {LANGUAGES.map((opt) => {
                const active = language === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => onLanguageChange(opt.value)}
                    data-testid={`er-v3-language-${opt.value}`}
                    className={[
                      "inline-flex items-center gap-[5px] rounded-full border px-3 py-[3px] font-mono text-[10.5px] uppercase tracking-[0.08em]",
                      active
                        ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.10)] text-[--color-accent-on]"
                        : "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]",
                    ].join(" ")}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </Section>
        </div>

        <div className="flex items-center justify-end gap-[8px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[12px]">
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="mb-[18px] last:mb-0">
      <h3 className="mb-[8px] font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
        {title}
      </h3>
      {children}
    </section>
  );
}

function RadioRow({
  active,
  label,
  hint,
  onSelect,
  testId,
}: {
  active: boolean;
  label: string;
  hint: string;
  onSelect: () => void;
  testId: string;
}): JSX.Element {
  return (
    <button
      type="button"
      onClick={onSelect}
      data-testid={testId}
      className={[
        "flex w-full items-start gap-[10px] rounded-md border px-[12px] py-[8px] text-left transition-colors",
        active
          ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
          : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
      ].join(" ")}
    >
      <span
        aria-hidden="true"
        className={[
          "mt-[3px] inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full border",
          active
            ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
            : "border-[--color-border-subtle] bg-[--color-bg-elevated]",
        ].join(" ")}
      >
        {active ? <Check size={10} strokeWidth={3} /> : null}
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-[13px] font-medium text-[--color-text-primary]">
          {label}
        </span>
        <span className="text-[11.5px] leading-[1.4] text-[--color-text-secondary]">
          {hint}
        </span>
      </span>
    </button>
  );
}
