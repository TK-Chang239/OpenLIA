/**
 * ReportSettingsModal — per-user Earnings Update v2 settings.
 *
 * Replaces the v1 section-toggle / custom-section editor. The v2 engine
 * is configured once per user (no per-run override): model, template,
 * data connectors, report length, language, and (Anthropic-only)
 * reasoning effort. Keeps the v1 modal chrome — Radix dialog, header,
 * scrollable body, footer Save/Cancel — for visual continuity.
 */
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, X } from "lucide-react";

import type { EuSettings, ReasoningEffort, ReportLength } from "../../api/earnings-update";
import { useEuTemplates } from "../../hooks/useEuTemplates";

import { EuModelPicker } from "./EuModelPicker";
import { EuTemplateUploadModal } from "./EuTemplateUploadModal";

interface Props {
  settings: EuSettings;
  onSave: (next: EuSettings) => Promise<unknown>;
  onClose: () => void;
}

const LENGTH_IDS: readonly ReportLength[] = ["concise", "normal", "elaborative"];
const LENGTH_LABELS: Record<ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

const REASONING_OPTIONS: readonly { value: ReasoningEffort; label: string }[] = [
  { value: null, label: "Default" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

function sectionTitle(text: string) {
  return (
    <h3 className="text-[15px] font-semibold text-[--color-text-primary] mb-1">
      {text}
    </h3>
  );
}

function Toggle({
  on,
  onClick,
  testId,
  label,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: string;
}) {
  return (
    <label className="flex items-center justify-between gap-4 px-4 py-3.5 cursor-pointer hover:bg-[--color-surface-hover] transition-colors">
      <span className="text-[13.5px] font-medium text-[--color-text-primary]">
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        data-testid={testId}
        onClick={onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on ? "bg-[--color-accent-primary]" : "bg-[--color-border-subtle]",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
            on ? "left-5" : "left-1",
          ].join(" ")}
        />
      </button>
    </label>
  );
}

export function ReportSettingsModal({ settings, onSave, onClose }: Props) {
  const [draft, setDraft] = useState<EuSettings>(settings);
  const [saving, setSaving] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const { templates, upload, remove } = useEuTemplates();

  // Built-in templates first, then user templates by name.
  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeTemplate = templates.find((t) => t.id === draft.template_id);

  async function handleUpload(name: string, markdown: string): Promise<void> {
    const created = await upload(name, markdown);
    setDraft((d) => ({ ...d, template_id: created.id }));
    setUploadOpen(false);
  }

  async function handleDeleteTemplate() {
    if (!activeTemplate || activeTemplate.is_builtin) return;
    await remove(activeTemplate.id);
    setDraft((d) => ({ ...d, template_id: "eu_default" }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      await onSave(draft);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  Earnings Update settings
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
                  Model, template &amp; data sources
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close settings"
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            {/* Model */}
            <section className="mb-7">
              {sectionTitle("Model")}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                The model used to write every Earnings Update report.
              </p>
              <EuModelPicker
                onChange={(sel) =>
                  sel &&
                  setDraft((d) => ({
                    ...d,
                    provider_kind: sel.provider_kind,
                    model: sel.model,
                  }))
                }
              />
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Template */}
            <section className="mb-7">
              {sectionTitle("Template")}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                The report skeleton. Upload your own to customize structure.
              </p>
              <div className="flex items-center gap-2">
                <select
                  value={draft.template_id}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, template_id: e.target.value }))
                  }
                  data-testid="eu-v2-template-select"
                  className="flex-1 h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
                >
                  {sortedTemplates.map((tpl) => (
                    <option key={tpl.id} value={tpl.id}>
                      {tpl.name}
                      {tpl.is_builtin ? "" : " (custom)"}
                    </option>
                  ))}
                </select>
                {activeTemplate && !activeTemplate.is_builtin ? (
                  <button
                    type="button"
                    onClick={() => void handleDeleteTemplate()}
                    aria-label="Delete template"
                    data-testid="eu-v2-template-delete"
                    className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-feedback-danger] hover:border-[--color-feedback-danger] transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setUploadOpen(true)}
                  data-testid="eu-v2-template-upload-open"
                  className="inline-flex items-center h-9 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px] whitespace-nowrap"
                >
                  Upload template
                </button>
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Connectors */}
            <section className="mb-7">
              {sectionTitle("Data sources")}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                Tools the engine may call while researching.
              </p>
              <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
                <Toggle
                  on={draft.financial_enabled}
                  onClick={() =>
                    setDraft((d) => ({ ...d, financial_enabled: !d.financial_enabled }))
                  }
                  testId="eu-v2-connector-financial"
                  label="Financial data (fundamentals, prices)"
                />
                <Toggle
                  on={draft.calendar_enabled}
                  onClick={() =>
                    setDraft((d) => ({ ...d, calendar_enabled: !d.calendar_enabled }))
                  }
                  testId="eu-v2-connector-calendar"
                  label="Earnings calendar"
                />
                <Toggle
                  on={draft.web_search_enabled}
                  onClick={() =>
                    setDraft((d) => ({
                      ...d,
                      web_search_enabled: !d.web_search_enabled,
                    }))
                  }
                  testId="eu-v2-connector-web_search"
                  label="Web search"
                />
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Length */}
            <section className="mb-7">
              {sectionTitle("Length")}
              <div
                role="radiogroup"
                aria-label="Report length"
                className="inline-flex gap-1 p-1 bg-[--color-surface-hover] rounded-lg mt-2"
              >
                {LENGTH_IDS.map((id) => {
                  const active = draft.length === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      role="radio"
                      aria-checked={active}
                      aria-label={id}
                      onClick={() => setDraft((d) => ({ ...d, length: id }))}
                      className={[
                        "px-3.5 py-1.5 rounded-md text-[13px] transition-all duration-[--duration-fast]",
                        active
                          ? "bg-[--color-bg-elevated] text-[--color-text-primary] font-medium shadow-sm"
                          : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
                      ].join(" ")}
                    >
                      {LENGTH_LABELS[id]}
                    </button>
                  );
                })}
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Language */}
            <section className={draft.provider_kind === "anthropic" ? "mb-7" : "mb-2"}>
              {sectionTitle("Language")}
              <select
                value={draft.language}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, language: e.target.value }))
                }
                data-testid="eu-v2-language-select"
                className="mt-2 h-9 w-[200px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
              >
                <option value="en">English</option>
                <option value="zh-Hant">繁體中文</option>
              </select>
            </section>

            {/* Reasoning effort — Anthropic only */}
            {draft.provider_kind === "anthropic" ? (
              <>
                <hr className="border-0 border-t border-[--color-border-subtle] my-7" />
                <section className="mb-2">
                  {sectionTitle("Reasoning effort")}
                  <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-2">
                    Higher effort yields deeper analysis at greater cost.
                  </p>
                  <select
                    value={draft.reasoning_effort ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        reasoning_effort: (e.target.value || null) as ReasoningEffort,
                      }))
                    }
                    data-testid="eu-v2-reasoning-select"
                    className="h-9 w-[200px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
                  >
                    {REASONING_OPTIONS.map((opt) => (
                      <option key={opt.label} value={opt.value ?? ""}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </section>
              </>
            ) : null}
          </div>

          <footer className="flex items-center justify-end gap-2 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong] transition-colors text-[13px] font-medium"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              data-testid="eu-v2-settings-save"
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>

      <EuTemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUpload={handleUpload}
      />
    </Dialog.Root>
  );
}
