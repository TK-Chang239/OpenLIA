/**
 * MbConfigFields — the shared Morning Briefing config controls.
 *
 * The model / template / instructions / connectors / length / language /
 * reasoning controls, lifted out of ScheduleEditorModal so both the schedule
 * editor and the Run Now modal render the exact same settings. Owns the
 * template/instructions/data-source hooks and the upload sub-modals; the
 * parent owns the draft state and passes a patcher via `onChange`.
 *
 * MB is purely template/instructions-driven — no ticker. The scheduling
 * fields (time/timezone/days/label/is_enabled) live only in the editor.
 */
import { useState, type ReactNode } from "react";
import { Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDataSource,
  MbReasoningEffort,
  MbReportLength,
} from "../../api/morning-briefing";
import { useMbDataSources } from "../../hooks/useMbDataSources";
import { useMbInstructions } from "../../hooks/useMbInstructions";
import { useMbTemplates } from "../../hooks/useMbTemplates";

import { MbInstructionsUploadModal } from "./MbInstructionsUploadModal";
import { MbModelPicker, type MbModelSelection } from "./MbModelPicker";
import { MbTemplateUploadModal } from "./MbTemplateUploadModal";

const LENGTH_IDS: readonly MbReportLength[] = [
  "concise",
  "normal",
  "elaborative",
];

/** The per-run config slice shared by the editor and the Run Now modal. */
export interface MbConfigDraft {
  template_id: string;
  instructions_id: string | null;
  provider_ids: string[];
  web_search: boolean;
  provider_kind: string | null;
  model: string | null;
  language: string;
  length: string;
  reasoning_effort: MbReasoningEffort;
}

/** Freeform template with no instructions has nothing to brief on. */
export function isBriefEmpty(draft: MbConfigDraft): boolean {
  return draft.template_id === "freeform" && !draft.instructions_id;
}

export function mbSectionTitle(text: string) {
  return (
    <h3 className="text-[15px] font-semibold text-[--color-text-primary] mb-1">
      {text}
    </h3>
  );
}

export function MbToggle({
  on,
  onClick,
  testId,
  label,
  ariaLabel,
  disabled = false,
}: {
  on: boolean;
  onClick: () => void;
  testId: string;
  label: ReactNode;
  ariaLabel?: string;
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
        aria-label={ariaLabel}
        data-testid={testId}
        disabled={disabled}
        onClick={disabled ? undefined : onClick}
        className={[
          "relative w-10 h-6 rounded-full flex-shrink-0 transition-colors",
          on && !disabled
            ? "bg-[--color-accent-primary]"
            : "bg-[--color-border-subtle]",
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

interface Props {
  draft: MbConfigDraft;
  onChange: (patch: Partial<MbConfigDraft>) => void;
}

export function MbConfigFields({ draft, onChange }: Props) {
  const { t } = useTranslation();
  const [uploadOpen, setUploadOpen] = useState(false);
  const [instructionsOpen, setInstructionsOpen] = useState(false);

  const {
    templates,
    create: createTemplate,
    upload: uploadTemplate,
    remove: removeTemplate,
  } = useMbTemplates();
  const {
    instructions,
    upload: uploadInstructions,
    remove: removeInstructions,
  } = useMbInstructions();
  const { sources } = useMbDataSources({
    provider_kind: draft.provider_kind ?? undefined,
    model: draft.model ?? undefined,
    enabled_provider_ids: draft.provider_ids,
    web_search: draft.web_search,
  });

  const LENGTH_LABELS: Record<MbReportLength, string> = {
    concise: t("morning_briefing.schedule_editor.length_concise"),
    normal: t("morning_briefing.schedule_editor.length_normal"),
    elaborative: t("morning_briefing.schedule_editor.length_elaborative"),
  };

  const REASONING_OPTIONS: readonly {
    value: MbReasoningEffort;
    label: string;
  }[] = [
    {
      value: null,
      label: t("morning_briefing.schedule_editor.reasoning_default"),
    },
    {
      value: "medium",
      label: t("morning_briefing.schedule_editor.reasoning_medium"),
    },
    {
      value: "high",
      label: t("morning_briefing.schedule_editor.reasoning_high"),
    },
  ];

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeTemplate = templates.find((tpl) => tpl.id === draft.template_id);

  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const activeInstructions = instructions.find(
    (ins) => ins.id === draft.instructions_id,
  );

  function handleModel(sel: MbModelSelection | null) {
    if (!sel) return;
    onChange({ provider_kind: sel.provider_kind, model: sel.model });
  }

  async function handleUploadMarkdown(name: string, markdown: string) {
    const created = await createTemplate({ name, source_markdown: markdown });
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleUploadFile(name: string, file: File) {
    const created = await uploadTemplate(name, file);
    onChange({ template_id: created.id });
    setUploadOpen(false);
  }

  async function handleDeleteTemplate() {
    if (!activeTemplate || activeTemplate.is_builtin) return;
    await removeTemplate(activeTemplate.id);
    onChange({ template_id: "freeform" });
  }

  async function handleUploadInstructions(name: string, file: File) {
    const created = await uploadInstructions(name, file);
    onChange({ instructions_id: created.id });
    setInstructionsOpen(false);
  }

  async function handleDeleteInstructions() {
    if (!activeInstructions || activeInstructions.is_builtin) return;
    if (
      !window.confirm(
        t("morning_briefing.schedule_editor.instructions_delete_confirm"),
      )
    ) {
      return;
    }
    await removeInstructions(activeInstructions.id);
    onChange({ instructions_id: null });
  }

  const isWebSearchSource = (s: MbDataSource) =>
    s.routing === "model_native" || s.key === "model_web_search";

  function sourceEnabled(s: MbDataSource): boolean {
    return isWebSearchSource(s)
      ? draft.web_search
      : draft.provider_ids.includes(s.key);
  }

  function toggleSource(s: MbDataSource): void {
    if (isWebSearchSource(s)) {
      onChange({ web_search: !draft.web_search });
      return;
    }
    const has = draft.provider_ids.includes(s.key);
    onChange({
      provider_ids: has
        ? draft.provider_ids.filter((k) => k !== s.key)
        : [...draft.provider_ids, s.key],
    });
  }

  function reasonText(s: MbDataSource): string | null {
    if (s.available || !s.unavailable_reason) return null;
    const key = `morning_briefing.schedule_editor.ds_reason_${s.unavailable_reason}`;
    const resolved = t(key);
    return resolved !== key
      ? resolved
      : t("morning_briefing.schedule_editor.ds_reason_unknown");
  }

  function categoryLabel(category: string): string {
    const key = `morning_briefing.schedule_editor.ds_category_${category}`;
    const resolved = t(key);
    return resolved !== key ? resolved : category;
  }

  function renderSource(s: MbDataSource) {
    const reason = reasonText(s);
    const label = (
      <span className="flex items-center gap-2">
        <span>{s.display_name}</span>
        <span className="inline-flex items-center rounded-full bg-[--color-surface-hover] px-2 py-0.5 text-[10px] font-medium uppercase tracking-[0.06em] text-[--color-text-tertiary]">
          {categoryLabel(s.category)}
        </span>
      </span>
    );
    return (
      <div key={s.key}>
        <MbToggle
          on={sourceEnabled(s) && s.available}
          onClick={() => toggleSource(s)}
          testId={`mb-connector-${s.key}`}
          label={label}
          ariaLabel={s.display_name}
          disabled={!s.available}
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
    <>
      {/* Model */}
      <section className="mb-7">
        {mbSectionTitle(t("morning_briefing.schedule_editor.model_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.model_hint")}
        </p>
        <MbModelPicker
          onChange={handleModel}
          value={{
            provider_kind: draft.provider_kind,
            model: draft.model,
          }}
        />
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Template */}
      <section className="mb-7">
        {mbSectionTitle(t("morning_briefing.schedule_editor.template_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.template_hint")}
        </p>
        <div className="flex items-center gap-2">
          <select
            value={draft.template_id}
            onChange={(e) => onChange({ template_id: e.target.value })}
            data-testid="mb-template-select"
            className="flex-1 h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          >
            <option value="freeform">
              {t("morning_briefing.schedule_editor.template_freeform")}
            </option>
            {sortedTemplates.map((tpl) => (
              <option key={tpl.id} value={tpl.id}>
                {tpl.name}
                {tpl.is_builtin
                  ? ""
                  : t("morning_briefing.schedule_editor.template_custom_suffix")}
              </option>
            ))}
          </select>
          {activeTemplate && !activeTemplate.is_builtin ? (
            <button
              type="button"
              onClick={() => void handleDeleteTemplate()}
              aria-label={t(
                "morning_briefing.schedule_editor.template_delete_aria",
              )}
              data-testid="mb-template-delete"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-feedback-danger] hover:border-[--color-feedback-danger] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            data-testid="mb-template-upload-open"
            className="inline-flex items-center h-9 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px] whitespace-nowrap"
          >
            {t("morning_briefing.schedule_editor.template_upload")}
          </button>
        </div>
        {draft.template_id === "freeform" ? (
          <p
            data-testid="mb-template-freeform-hint"
            className="mt-3 text-[12px] text-[--color-text-tertiary] leading-[1.5]"
          >
            {t("morning_briefing.schedule_editor.template_freeform_hint")}
          </p>
        ) : null}
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Instructions */}
      <section className="mb-7">
        {mbSectionTitle(t("morning_briefing.schedule_editor.instructions_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.instructions_hint")}
        </p>
        <div className="flex items-center gap-2">
          <select
            value={draft.instructions_id ?? ""}
            onChange={(e) =>
              onChange({ instructions_id: e.target.value || null })
            }
            data-testid="mb-instructions-select"
            className="flex-1 h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
          >
            <option value="">
              {t("morning_briefing.schedule_editor.instructions_none")}
            </option>
            {sortedInstructions.map((ins) => (
              <option key={ins.id} value={ins.id}>
                {ins.name}
                {ins.is_builtin
                  ? ""
                  : t(
                      "morning_briefing.schedule_editor.instructions_custom_suffix",
                    )}
              </option>
            ))}
          </select>
          {activeInstructions && !activeInstructions.is_builtin ? (
            <button
              type="button"
              onClick={() => void handleDeleteInstructions()}
              aria-label={t(
                "morning_briefing.schedule_editor.instructions_delete_aria",
              )}
              data-testid="mb-instructions-delete"
              className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-feedback-danger] hover:border-[--color-feedback-danger] transition-colors"
            >
              <Trash2 size={14} />
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setInstructionsOpen(true)}
            data-testid="mb-instructions-upload-open"
            className="inline-flex items-center h-9 px-3 border border-[--color-border-subtle] rounded-md bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors text-[12.5px] whitespace-nowrap"
          >
            {t("morning_briefing.schedule_editor.instructions_upload")}
          </button>
        </div>
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Connectors */}
      <section className="mb-7">
        {mbSectionTitle(t("morning_briefing.schedule_editor.connectors_title"))}
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.connectors_hint")}
        </p>
        {sources && sources.length === 0 ? (
          <p
            data-testid="mb-data-sources-empty"
            className="text-[13px] text-[--color-text-tertiary] leading-[1.5] border border-[--color-border-subtle] rounded-lg px-4 py-3"
          >
            {t("morning_briefing.schedule_editor.ds_empty")}
          </p>
        ) : (
          <div className="border border-[--color-border-subtle] rounded-lg overflow-hidden divide-y divide-[--color-border-subtle]">
            {(sources ?? []).map((s) => renderSource(s))}
          </div>
        )}
      </section>

      <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

      {/* Length */}
      <section className="mb-7">
        {mbSectionTitle(t("morning_briefing.schedule_editor.length_title"))}
        <div
          role="radiogroup"
          aria-label={t("morning_briefing.schedule_editor.length_aria")}
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
                onClick={() => onChange({ length: id })}
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
        {mbSectionTitle(t("morning_briefing.schedule_editor.language_title"))}
        <select
          value={draft.language}
          onChange={(e) => onChange({ language: e.target.value })}
          data-testid="mb-language-select"
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
            {mbSectionTitle(t("morning_briefing.schedule_editor.reasoning_title"))}
            <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-2">
              {t("morning_briefing.schedule_editor.reasoning_hint")}
            </p>
            <select
              value={draft.reasoning_effort ?? ""}
              onChange={(e) =>
                onChange({
                  reasoning_effort: (e.target.value ||
                    null) as MbReasoningEffort,
                })
              }
              data-testid="mb-reasoning-select"
              className="h-9 w-[200px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            >
              {REASONING_OPTIONS.map((opt) => (
                <option key={opt.value ?? "null"} value={opt.value ?? ""}>
                  {opt.label}
                </option>
              ))}
            </select>
          </section>
        </>
      ) : null}

      <MbTemplateUploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onUploadMarkdown={handleUploadMarkdown}
        onUploadFile={handleUploadFile}
      />

      <MbInstructionsUploadModal
        open={instructionsOpen}
        onClose={() => setInstructionsOpen(false)}
        onUpload={handleUploadInstructions}
      />
    </>
  );
}
