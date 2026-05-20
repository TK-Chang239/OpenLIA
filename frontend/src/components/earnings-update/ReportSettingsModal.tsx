import { useMemo, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

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

const LENGTH_IDS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

function randomId(): string {
  return `custom_${Math.random().toString(36).slice(2, 8)}_${Date.now().toString(36)}`;
}

export function ReportSettingsModal({ open, config, onClose, onSave }: Props) {
  const { t } = useTranslation();
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
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  {t("earnings.settings_modal.title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
                  {t("earnings.settings_modal.subtitle")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("earnings.settings_modal.close_aria")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            <section className="mb-7">
              <h3 className="text-[15px] font-semibold text-[--color-text-primary] mb-1">
                {t("earnings.settings_modal.length_title")}
              </h3>
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.length_hint")}
              </p>
              <div
                role="radiogroup"
                aria-label={t("earnings.settings_modal.length_aria")}
                className="inline-flex gap-1 p-1 bg-[--color-surface-hover] rounded-lg"
              >
                {LENGTH_IDS.map((id) => {
                  const active = length === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      aria-label={id}
                      onClick={() => setLength(id)}
                      className={[
                        "px-3.5 py-1.5 rounded-md text-[13px] transition-all duration-[--duration-fast]",
                        active
                          ? "bg-[--color-bg-elevated] text-[--color-text-primary] font-medium shadow-sm"
                          : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
                      ].join(" ")}
                    >
                      {t(`earnings.settings_modal.length_${id}`)}
                    </button>
                  );
                })}
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            <section className="mb-7">
              <h3 className="text-[15px] font-semibold text-[--color-text-primary] mb-1">
                {t("earnings.settings_modal.sections_title")}
              </h3>
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.sections_hint")}
              </p>
              <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden">
                {defaultRows.map((row, idx) => {
                  const on = enabled.has(row.id);
                  return (
                    <label
                      key={row.id}
                      className={[
                        "flex items-center justify-between gap-4 px-4 py-3.5 cursor-pointer hover:bg-[--color-surface-hover] transition-colors",
                        idx < defaultRows.length - 1
                          ? "border-b border-[--color-border-subtle]"
                          : "",
                      ].join(" ")}
                    >
                      <div className="flex flex-col gap-0.5 min-w-0">
                        <span className="text-[13.5px] font-medium text-[--color-text-primary]">
                          {row.title}
                        </span>
                        <span className="text-[12px] text-[--color-text-secondary] leading-[1.4]">
                          {row.description}
                        </span>
                      </div>
                      <span
                        role="switch"
                        aria-checked={on}
                        className={[
                          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
                          on
                            ? "bg-[--color-accent-primary]"
                            : "bg-[--color-border-subtle]",
                        ].join(" ")}
                      >
                        <span
                          className={[
                            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
                            on ? "left-5" : "left-1",
                          ].join(" ")}
                        />
                      </span>
                      <input
                        type="checkbox"
                        aria-label={row.title}
                        checked={on}
                        onChange={() => toggle(row.id)}
                        className="sr-only"
                      />
                    </label>
                  );
                })}
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            <section className="mb-2">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-[15px] font-semibold text-[--color-text-primary]">
                  {t("earnings.settings_modal.custom_title")}
                </h3>
                <button
                  type="button"
                  onClick={addCustom}
                  className="inline-flex items-center h-8 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px]"
                >
                  {t("earnings.settings_modal.custom_button")}
                </button>
              </div>
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.custom_hint")}
              </p>
              {customs.length === 0 ? (
                <div className="border border-dashed border-[--color-border-subtle] rounded-md px-4 py-6 text-center text-[12.5px] text-[--color-text-tertiary]">
                  {t("earnings.settings_modal.custom_empty")}
                </div>
              ) : (
                customs.map((c, idx) => (
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
                ))
              )}
            </section>
          </div>

          <footer className="flex items-center justify-end gap-2 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong] transition-colors text-[13px] font-medium"
            >
              {t("earnings.settings_modal.cancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {saving
                ? t("earnings.settings_modal.saving")
                : t("earnings.settings_modal.save")}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
