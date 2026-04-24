import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

import {
  CustomSection,
  EuConfig,
  ReportLength,
} from "../../api/earnings-update";
import {
  DEFAULT_EU_SECTIONS,
  EU_SECTION_CATALOG,
} from "../../lib/earnings-update/section-catalog";

import { CustomSectionRow } from "./CustomSectionRow";

interface Props {
  open: boolean;
  config: EuConfig;
  onClose: () => void;
  onSave: (next: EuConfig) => Promise<void>;
}

const LENGTHS: ReportLength[] = ["concise", "normal", "elaborative"];

function randomId(): string {
  return `custom_${Math.random().toString(36).slice(2, 8)}_${Date.now().toString(36)}`;
}

export function ReportSettingsModal({ open, config, onClose, onSave }: Props) {
  const [length, setLength] = useState<ReportLength>(config.report_length);
  const [enabled, setEnabled] = useState<Set<string>>(
    new Set(config.enabled_section_ids),
  );
  const [customs, setCustoms] = useState<CustomSection[]>(
    config.custom_sections,
  );
  const [saving, setSaving] = useState(false);

  const defaultRows = useMemo(
    () =>
      DEFAULT_EU_SECTIONS.map((id) => ({
        id,
        title: EU_SECTION_CATALOG[id].title,
        description: EU_SECTION_CATALOG[id].description,
      })),
    [],
  );

  function toggle(id: string) {
    setEnabled((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function addCustom() {
    setCustoms((prev) => [
      ...prev,
      { id: randomId(), title: "", description: "" },
    ]);
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: EuConfig = {
        report_length: length,
        enabled_section_ids: [
          ...DEFAULT_EU_SECTIONS.filter((id) => enabled.has(id)),
          ...customs.map((c) => c.id),
        ],
        custom_sections: customs.filter((c) => c.title.trim()),
      };
      await onSave(payload);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[560px] max-h-[85vh] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg overflow-y-auto">
          <Dialog.Title className="text-lg font-semibold mb-4">
            Report Settings
          </Dialog.Title>

          <section className="mb-4">
            <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em] mb-2">
              Report Length
            </h4>
            <div className="flex gap-2">
              {LENGTHS.map((l) => (
                <label key={l} className="text-sm flex items-center gap-1">
                  <input
                    type="radio"
                    name="length"
                    checked={length === l}
                    onChange={() => setLength(l)}
                    aria-label={l}
                  />
                  {l[0].toUpperCase() + l.slice(1)}
                </label>
              ))}
            </div>
          </section>

          <section className="mb-4">
            <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em] mb-2">
              Sections
            </h4>
            {defaultRows.map((row) => (
              <label
                key={row.id}
                className="flex items-start gap-2 text-sm mb-2"
              >
                <input
                  type="checkbox"
                  aria-label={row.title}
                  checked={enabled.has(row.id)}
                  onChange={() => toggle(row.id)}
                />
                <span>
                  <strong>{row.title}</strong>
                  <span className="text-[--color-text-secondary]">
                    {" "}— {row.description}
                  </span>
                </span>
              </label>
            ))}
          </section>

          <section className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-xs uppercase text-[--color-text-tertiary] tracking-[0.04em]">
                Custom Sections
              </h4>
              <button
                type="button"
                onClick={addCustom}
                className="text-sm text-[--color-accent-primary]"
              >
                + Custom Section
              </button>
            </div>
            {customs.map((c, idx) => (
              <CustomSectionRow
                key={c.id}
                value={c}
                onChange={(next) =>
                  setCustoms((prev) =>
                    prev.map((x, i) => (i === idx ? next : x)),
                  )
                }
                onRemove={() =>
                  setCustoms((prev) => prev.filter((_, i) => i !== idx))
                }
              />
            ))}
          </section>

          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover] disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
