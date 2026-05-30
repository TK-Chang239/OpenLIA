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
import { useTranslation } from "react-i18next";

import type {
  DataSourceSlot,
  EuSettings,
  ReasoningEffort,
  ReportLength,
} from "../../api/earnings-update";
import { useEuDataSources } from "../../hooks/useEuDataSources";
import { useEuTemplates } from "../../hooks/useEuTemplates";

import { EuModelPicker } from "./EuModelPicker";
import { EuTemplateUploadModal } from "./EuTemplateUploadModal";

interface Props {
  settings: EuSettings;
  onSave: (next: EuSettings) => Promise<unknown>;
  onClose: () => void;
}

const LENGTH_IDS: readonly ReportLength[] = ["concise", "normal", "elaborative"];

const REASONING_EFFORT_VALUES: readonly ReasoningEffort[] = [null, "medium", "high"];

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
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: string;
  disabled?: boolean;
}) {
  return (
    <label
      className={[
        "flex items-center justify-between gap-4 px-4 py-3.5 transition-colors",
        disabled
          ? "opacity-50 cursor-not-allowed pointer-events-none"
          : "cursor-pointer hover:bg-[--color-surface-hover]",
      ].join(" ")}
    >
      <span className="text-[13.5px] font-medium text-[--color-text-primary]">
        {label}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label={label}
        data-testid={testId}
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on && !disabled ? "bg-[--color-accent-primary]" : "bg-[--color-border-subtle]",
        ].join(" ")}
      >
        <span
          className={[
            "absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-[left]",
            on && !disabled ? "left-5" : "left-1",
          ].join(" ")}
        />
      </button>
    </label>
  );
}

export function ReportSettingsModal({ settings, onSave, onClose }: Props) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState<EuSettings>(settings);
  const [saving, setSaving] = useState(false);
  const [uploadOpen, setUploadOpen] = useState(false);
  const { templates, upload, remove } = useEuTemplates();
  const { dataSources } = useEuDataSources(draft.provider_kind, draft.model);

  const LENGTH_LABELS: Record<ReportLength, string> = {
    concise: t("earnings.settings_modal.length_concise"),
    normal: t("earnings.settings_modal.length_normal"),
    elaborative: t("earnings.settings_modal.length_elaborative"),
  };

  const REASONING_OPTIONS: readonly { value: ReasoningEffort; label: string }[] = [
    { value: null, label: t("earnings.settings_modal.reasoning_default") },
    { value: "medium", label: t("earnings.settings_modal.reasoning_medium") },
    { value: "high", label: t("earnings.settings_modal.reasoning_high") },
  ];

  // Built-in templates first, then user templates by name.
  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeTemplate = templates.find((tpl) => tpl.id === draft.template_id);

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
      const sanitized: EuSettings = {
        ...draft,
        financial_enabled: draft.financial_enabled && !!dataSources?.financial.available,
        calendar_enabled:
          draft.calendar_enabled && !!dataSources?.earnings_calendar.available,
        web_search_enabled: draft.web_search_enabled && !!dataSources?.web_search.available,
      };
      await onSave(sanitized);
      onClose();
    } finally {
      setSaving(false);
    }
  }

  function slotLabel(
    base: string,
    slot: DataSourceSlot | undefined,
    isWebSearch: boolean,
  ): string {
    if (!slot?.available || !slot.provider_label) return base;
    const provider = isWebSearch
      ? t("earnings.settings_modal.ds_via", { provider: slot.provider_label })
      : slot.provider_label;
    return `${base} · ${provider}`;
  }

  function reasonText(slot: DataSourceSlot | undefined): string | null {
    if (!slot || slot.available || !slot.unavailable_reason) return null;
    const key = `earnings.settings_modal.ds_reason_${slot.unavailable_reason}`;
    const resolved = t(key);
    // i18next returns the key itself when the translation is missing.
    return resolved !== key ? resolved : t("earnings.settings_modal.ds_reason_unknown");
  }

  function renderSlot(
    base: string,
    slot: DataSourceSlot | undefined,
    enabled: boolean,
    onToggle: () => void,
    testId: string,
    isWebSearch = false,
  ) {
    const reason = reasonText(slot);
    return (
      <div key={testId}>
        <Toggle
          on={enabled && !!slot?.available}
          onClick={onToggle}
          testId={testId}
          label={slotLabel(base, slot, isWebSearch)}
          disabled={!slot?.available}
        />
        {reason ? (
          <p className="px-4 pb-3 -mt-1 text-[12px] text-[--color-text-tertiary] leading-[1.4]">
            {reason}
          </p>
        ) : null}
      </div>
    );
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
                  {t("earnings.settings_modal.v2_title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
                  {t("earnings.settings_modal.v2_subtitle")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("earnings.settings_modal.v2_close_aria")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            {/* Model */}
            <section className="mb-7">
              {sectionTitle(t("earnings.settings_modal.model_title"))}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.model_hint")}
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
              {sectionTitle(t("earnings.settings_modal.template_title"))}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.template_hint")}
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
                      {tpl.is_builtin ? "" : t("earnings.settings_modal.template_custom_suffix")}
                    </option>
                  ))}
                </select>
                {activeTemplate && !activeTemplate.is_builtin ? (
                  <button
                    type="button"
                    onClick={() => void handleDeleteTemplate()}
                    aria-label={t("earnings.settings_modal.template_delete_aria")}
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
                  {t("earnings.settings_modal.template_upload")}
                </button>
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Connectors */}
            <section className="mb-7">
              {sectionTitle(t("earnings.settings_modal.connectors_title"))}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("earnings.settings_modal.connectors_hint")}
              </p>
              {dataSources &&
              !dataSources.financial.available &&
              !dataSources.earnings_calendar.available &&
              !dataSources.web_search.available ? (
                <p
                  data-testid="eu-v2-data-sources-empty"
                  className="text-[13px] text-[--color-text-tertiary] leading-[1.5] border border-[--color-border-subtle] rounded-lg px-4 py-3"
                >
                  {t("earnings.settings_modal.ds_empty")}
                </p>
              ) : (
                <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
                  {renderSlot(
                    t("earnings.settings_modal.connector_financial"),
                    dataSources?.financial,
                    draft.financial_enabled,
                    () =>
                      setDraft((d) => ({ ...d, financial_enabled: !d.financial_enabled })),
                    "eu-v2-connector-financial",
                  )}
                  {renderSlot(
                    t("earnings.settings_modal.connector_calendar"),
                    dataSources?.earnings_calendar,
                    draft.calendar_enabled,
                    () =>
                      setDraft((d) => ({ ...d, calendar_enabled: !d.calendar_enabled })),
                    "eu-v2-connector-calendar",
                  )}
                  {renderSlot(
                    t("earnings.settings_modal.connector_web_search"),
                    dataSources?.web_search,
                    draft.web_search_enabled,
                    () =>
                      setDraft((d) => ({
                        ...d,
                        web_search_enabled: !d.web_search_enabled,
                      })),
                    "eu-v2-connector-web_search",
                    true,
                  )}
                </div>
              )}
              {dataSources && dataSources.other_connectors.length > 0 ? (
                <p
                  data-testid="eu-v2-data-sources-other"
                  className="mt-3 text-[12px] text-[--color-text-tertiary] leading-[1.5]"
                >
                  {t("earnings.settings_modal.ds_other_configured", {
                    names: dataSources.other_connectors.map((c) => c.display_name).join(", "),
                  })}
                </p>
              ) : null}
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Length */}
            <section className="mb-7">
              {sectionTitle(t("earnings.settings_modal.length_section_title"))}
              <div
                role="radiogroup"
                aria-label={t("earnings.settings_modal.length_aria")}
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
              {sectionTitle(t("earnings.settings_modal.language_title"))}
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
                  {sectionTitle(t("earnings.settings_modal.reasoning_title"))}
                  <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-2">
                    {t("earnings.settings_modal.reasoning_hint")}
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
                    {REASONING_OPTIONS.map((opt, i) => (
                      <option key={REASONING_EFFORT_VALUES[i] ?? "null"} value={opt.value ?? ""}>
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
              {t("earnings.settings_modal.cancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving}
              data-testid="eu-v2-settings-save"
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {saving ? t("earnings.settings_modal.v2_saving") : t("earnings.settings_modal.v2_save")}
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
