import * as Dialog from "@radix-ui/react-dialog";
import { Check, Plus, X } from "lucide-react";
import { type JSX, useEffect, useState } from "react";

import {
  type CustomSection,
  type ErConfig,
  type ErConfigPatch,
  type ReportLength,
  type ReportMode,
} from "../../api/equity-research";
import { SECTION_CATALOG } from "../../lib/equity-research/section-catalog";
import { CustomSectionRow } from "./CustomSectionRow";

const MODE_LABELS: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
};
const MODE_FULL_LABEL: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation Report",
  stock_update: "Stock Update Report",
  sector_research: "Sector Research Report",
};
const LENGTH_LABELS: Record<ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

interface Props {
  open: boolean;
  config: ErConfig;
  onClose: () => void;
  onSave: (patch: ErConfigPatch) => Promise<void>;
}

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

export function ReportSettingsModal({
  open,
  config,
  onClose,
  onSave,
}: Props): JSX.Element {
  const [mode, setMode] = useState<ReportMode>(config.report_mode);
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [sections, setSections] = useState(config.sections_by_mode);
  const [customs, setCustoms] = useState(config.custom_sections_by_mode);
  const [pendingCustom, setPendingCustom] = useState<CustomSection | null>(null);

  useEffect(() => {
    if (!open) return;
    setMode(config.report_mode);
    setLength(config.report_length);
    setSections(config.sections_by_mode);
    setCustoms(config.custom_sections_by_mode);
    setPendingCustom(null);
  }, [open, config]);

  const toggleSection = (id: string) => {
    const current = new Set(sections[mode]);
    if (current.has(id)) current.delete(id);
    else current.add(id);
    const ordered = SECTION_CATALOG[mode]
      .map((s) => s.id)
      .filter((sid) => current.has(sid));
    setSections({ ...sections, [mode]: ordered });
  };

  const addCustom = () => {
    if (!pendingCustom?.title) return;
    const id = `custom_${pendingCustom.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "_")
      .slice(0, 32)}_${Math.random().toString(36).slice(2, 6)}`;
    setCustoms({
      ...customs,
      [mode]: [...customs[mode], { ...pendingCustom, id }],
    });
    setPendingCustom(null);
  };

  const save = async () => {
    await onSave({
      report_mode: mode,
      report_length: length,
      sections_by_mode: sections,
      custom_sections_by_mode: customs,
    });
    onClose();
  };

  const modeOptions = (Object.keys(MODE_LABELS) as ReportMode[]).map((v) => ({
    value: v,
    label: MODE_LABELS[v],
  }));
  const lengthOptions = (Object.keys(LENGTH_LABELS) as ReportLength[]).map(
    (v) => ({ value: v, label: LENGTH_LABELS[v] }),
  );

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-full max-w-[520px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]">
          <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <Dialog.Title className="m-0 text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
              Report Settings
            </Dialog.Title>
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
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                Report Mode
              </span>
              <Segmented
                ariaLabel="Report Mode"
                value={mode}
                options={modeOptions}
                onChange={setMode}
              />
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                Report Length
              </span>
              <Segmented
                ariaLabel="Report Length"
                value={length}
                options={lengthOptions}
                onChange={setLength}
              />
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                Sections ·{" "}
                <strong className="font-medium text-[--color-text-primary]">
                  {MODE_FULL_LABEL[mode]}
                </strong>
              </span>
              <ul className="m-0 mt-1 flex list-none flex-col p-0">
                {SECTION_CATALOG[mode].map((s, idx) => {
                  const checked = sections[mode].includes(s.id);
                  const last = idx === SECTION_CATALOG[mode].length - 1;
                  return (
                    <li
                      key={s.id}
                      className={[
                        "group flex cursor-pointer items-center gap-[10px] py-[9px]",
                        last
                          ? ""
                          : "border-b border-dashed border-[--color-border-subtle]",
                      ].join(" ")}
                      onClick={() => toggleSection(s.id)}
                    >
                      <span
                        aria-hidden="true"
                        className={[
                          "inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-[4px] border-[1.5px] transition-colors",
                          checked
                            ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                            : "border-[--color-border-strong]",
                        ].join(" ")}
                      >
                        {checked ? (
                          <Check size={10} strokeWidth={3} />
                        ) : null}
                      </span>
                      <span className="w-5 font-mono text-[10px] tracking-[0.04em] text-[--color-text-tertiary]">
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <span className="flex-1 text-[13.5px] text-[--color-text-primary] transition-colors group-hover:text-[--color-feedback-success]">
                        {s.title}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </section>

            <section className="px-[22px] py-[18px]">
              <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                Custom Sections
              </span>
              {customs[mode].map((c, i) => (
                <CustomSectionRow
                  key={c.id}
                  section={c}
                  onChange={(next) => {
                    const copy = [...customs[mode]];
                    copy[i] = next;
                    setCustoms({ ...customs, [mode]: copy });
                  }}
                  onRemove={() => {
                    const copy = customs[mode].filter((_, j) => j !== i);
                    setCustoms({ ...customs, [mode]: copy });
                  }}
                />
              ))}
              {pendingCustom ? (
                <div className="mb-2 space-y-2 rounded-md border border-[--color-border-subtle] p-2">
                  <input
                    aria-label="New custom section title"
                    placeholder="Title"
                    autoFocus
                    className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
                    value={pendingCustom.title}
                    onChange={(e) =>
                      setPendingCustom({
                        ...pendingCustom,
                        title: e.target.value,
                      })
                    }
                  />
                  <textarea
                    aria-label="New custom section description"
                    placeholder="Description (optional)"
                    rows={2}
                    className="w-full rounded-sm border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
                    value={pendingCustom.description ?? ""}
                    onChange={(e) =>
                      setPendingCustom({
                        ...pendingCustom,
                        description: e.target.value || null,
                      })
                    }
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setPendingCustom(null)}
                      className="h-7 px-2 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={addCustom}
                      disabled={!pendingCustom.title}
                      className="h-7 rounded-sm bg-[--color-accent-primary] px-2 text-sm text-[--color-accent-on] disabled:opacity-40"
                    >
                      Add section
                    </button>
                  </div>
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() =>
                    setPendingCustom({ id: "", title: "", description: null })
                  }
                  className="inline-flex h-7 items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-all hover:border-solid hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
                >
                  <Plus size={11} strokeWidth={2} />
                  Add custom section
                </button>
              )}
            </section>
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
              className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
            >
              Save Settings
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
