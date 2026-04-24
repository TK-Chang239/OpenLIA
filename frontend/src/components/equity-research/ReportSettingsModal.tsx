import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import { X } from "lucide-react";

import {
  type CustomSection,
  type ErConfig,
  type ErConfigPatch,
  type ReportLength,
  type ReportMode,
} from "../../api/equity-research";
import { ModeToggle } from "./ModeToggle";
import { CustomSectionRow } from "./CustomSectionRow";
import { SECTION_CATALOG } from "../../lib/equity-research/section-catalog";

const MODE_LABELS: Record<ReportMode, string> = {
  stock_initiation: "Stock Initiation",
  stock_update: "Stock Update",
  sector_research: "Sector Research",
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

export function ReportSettingsModal({ open, config, onClose, onSave }: Props) {
  const [mode, setMode] = useState<ReportMode>(config.report_mode);
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [sections, setSections] = useState(config.sections_by_mode);
  const [customs, setCustoms] = useState(config.custom_sections_by_mode);
  const [pendingCustom, setPendingCustom] = useState<CustomSection | null>(null);

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
    const added = { ...pendingCustom, id };
    setCustoms({
      ...customs,
      [mode]: [...customs[mode], added],
    });
    setPendingCustom(null);
  };

  const save = async () => {
    const patch: ErConfigPatch = {
      report_mode: mode,
      report_length: length,
      sections_by_mode: sections,
      custom_sections_by_mode: customs,
    };
    await onSave(patch);
    onClose();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[480px] rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg">
          <div className="flex items-center justify-between px-6 py-4 border-b border-[--color-border-subtle]">
            <Dialog.Title className="text-lg font-semibold">
              Report Settings
            </Dialog.Title>
            <button onClick={onClose} aria-label="Close">
              <X size={16} />
            </button>
          </div>

          <div className="px-6 py-4 space-y-4">
            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Report Mode
              </label>
              <div className="mt-1">
                <ModeToggle
                  ariaLabel="Report Mode"
                  value={mode}
                  options={(Object.keys(MODE_LABELS) as ReportMode[]).map((v) => ({
                    value: v,
                    label: MODE_LABELS[v],
                  }))}
                  onChange={setMode}
                />
              </div>
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Report Length
              </label>
              <div className="mt-1">
                <ModeToggle
                  ariaLabel="Report Length"
                  value={length}
                  options={(Object.keys(LENGTH_LABELS) as ReportLength[]).map((v) => ({
                    value: v,
                    label: LENGTH_LABELS[v],
                  }))}
                  onChange={setLength}
                />
              </div>
            </div>

            <div>
              <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                Sections ({MODE_LABELS[mode]} Report)
              </label>
              <ul className="mt-2 divide-y divide-[--color-border-subtle] border border-[--color-border-subtle] rounded-[--radius-md]">
                {SECTION_CATALOG[mode].map((s) => {
                  const checked = sections[mode].includes(s.id);
                  return (
                    <li key={s.id} className="px-3 py-2 flex items-center gap-2">
                      <input
                        type="checkbox"
                        id={`sec-${s.id}`}
                        checked={checked}
                        onChange={() => toggleSection(s.id)}
                      />
                      <label htmlFor={`sec-${s.id}`} className="text-sm">
                        {s.title}
                      </label>
                    </li>
                  );
                })}
              </ul>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label className="text-xs uppercase tracking-wide text-[--color-text-tertiary]">
                  Custom Sections
                </label>
                {!pendingCustom && (
                  <button
                    type="button"
                    className="text-sm text-[--color-accent-primary]"
                    onClick={() =>
                      setPendingCustom({ id: "", title: "", description: null })
                    }
                  >
                    + Add
                  </button>
                )}
              </div>
              <div className="mt-2">
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
                {pendingCustom && (
                  <div className="border border-[--color-border-subtle] rounded-[--radius-md] p-2 space-y-2">
                    <input
                      aria-label="New custom section title"
                      placeholder="Title"
                      className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-sm"
                      value={pendingCustom.title}
                      onChange={(e) =>
                        setPendingCustom({ ...pendingCustom, title: e.target.value })
                      }
                    />
                    <textarea
                      aria-label="New custom section description"
                      placeholder="Description (optional)"
                      rows={2}
                      className="w-full rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 py-1 text-xs"
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
                        className="text-sm px-2 h-7"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={addCustom}
                        disabled={!pendingCustom.title}
                        className="text-sm px-2 h-7 rounded-[--radius-sm] bg-[--color-accent-primary] text-white disabled:opacity-40"
                      >
                        Add section
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t border-[--color-border-subtle]">
            <button
              type="button"
              onClick={onClose}
              className="h-9 px-4 rounded-[--radius-md] border border-[--color-border-subtle]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              className="h-9 px-4 rounded-[--radius-md] bg-[--color-accent-primary] text-white"
            >
              Save settings
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
