/**
 * V3ReportSettingsModal — v3 equivalent of the v2 ReportSettingsModal.
 *
 * Same visual structure as ``components/equity-research/ReportSettingsModal``
 * (Radix dialog, segmented controls, section dividers, footer with
 * Cancel/Save buttons) so the v3 page chrome matches v1/v2 pixel-for-
 * pixel. v3-specific dials only — reasoning effort and template
 * picker render as disabled placeholder sections so the visual slot
 * exists today and PR2/PR3 just need to drop in the working
 * controls without re-laying-out the modal.
 *
 * Settings state is staged locally; ``onSave`` fires only on Save
 * (matches v2 behaviour, where Cancel reverts to the modal-open
 * snapshot of config).
 */
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { type JSX, useEffect, useState } from "react";

import type {
  V3Language,
  V3ReportLength,
  V3ReportType,
} from "../../api/equity-research-v3";

export interface V3SettingsValue {
  reportType: V3ReportType;
  length: V3ReportLength;
  language: V3Language;
}

interface Props {
  open: boolean;
  value: V3SettingsValue;
  onClose: () => void;
  onSave: (next: V3SettingsValue) => void;
}

const REPORT_TYPE_OPTIONS: { value: V3ReportType; label: string }[] = [
  { value: "initiation", label: "Stock Initiation" },
  { value: "update", label: "Stock Update" },
  { value: "sector_research", label: "Sector Research" },
];

const REPORT_TYPE_FULL_LABEL: Record<V3ReportType, string> = {
  initiation: "Stock Initiation Report",
  update: "Stock Update Report",
  sector_research: "Sector Research Report",
};

const LENGTH_OPTIONS: { value: V3ReportLength; label: string }[] = [
  { value: "concise", label: "Concise" },
  { value: "normal", label: "Normal" },
  { value: "elaborative", label: "Elaborative" },
];

const LANGUAGE_OPTIONS: { value: V3Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "zh-TW", label: "繁體中文" },
];

interface SegmentedProps<T extends string> {
  ariaLabel: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (next: T) => void;
}

function Segmented<T extends string>({
  ariaLabel,
  value,
  options,
  onChange,
}: SegmentedProps<T>): JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={[
              "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
              active
                ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function SectionHeader({ label }: { label: string }): JSX.Element {
  return (
    <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
      {label}
    </span>
  );
}

function ComingSoon({
  label,
  hint,
}: {
  label: string;
  hint: string;
}): JSX.Element {
  return (
    <section
      data-testid={`er-v3-settings-coming-soon-${label.toLowerCase().replace(/\s+/g, "-")}`}
      className="border-b border-[--color-border-subtle] px-[22px] py-[18px] opacity-60"
    >
      <SectionHeader label={label} />
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2">
        <span className="text-[12.5px] text-[--color-text-secondary]">{hint}</span>
        <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          Coming soon
        </span>
      </div>
    </section>
  );
}

export function V3ReportSettingsModal({
  open,
  value,
  onClose,
  onSave,
}: Props): JSX.Element {
  const [reportType, setReportType] = useState<V3ReportType>(value.reportType);
  const [length, setLength] = useState<V3ReportLength>(value.length);
  const [language, setLanguage] = useState<V3Language>(value.language);

  useEffect(() => {
    if (!open) return;
    setReportType(value.reportType);
    setLength(value.length);
    setLanguage(value.language);
  }, [open, value.reportType, value.length, value.language]);

  const save = () => {
    onSave({ reportType, length, language });
    onClose();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
        <Dialog.Content
          data-testid="er-v3-settings-modal"
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-full max-w-[520px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        >
          <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <Dialog.Title className="m-0 text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
              Report settings
            </Dialog.Title>
            <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              v3 engine
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <SectionHeader label="Report type" />
              <Segmented
                ariaLabel="Report type"
                value={reportType}
                options={REPORT_TYPE_OPTIONS}
                onChange={setReportType}
              />
              <p className="mt-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
                {REPORT_TYPE_FULL_LABEL[reportType]}
              </p>
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <SectionHeader label="Length" />
              <Segmented
                ariaLabel="Length"
                value={length}
                options={LENGTH_OPTIONS}
                onChange={setLength}
              />
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <SectionHeader label="Language" />
              <Segmented
                ariaLabel="Language"
                value={language}
                options={LANGUAGE_OPTIONS}
                onChange={setLanguage}
              />
            </section>

            <ComingSoon
              label="Reasoning effort"
              hint="Off / Medium / High — extended thinking knob."
            />

            <ComingSoon
              label="Template"
              hint="Pick a built-in template or upload your own."
            />
          </div>

          <div className="flex justify-end gap-2 rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[14px]">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-4 font-display text-[13.5px] font-medium text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              data-testid="er-v3-settings-save"
              className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
