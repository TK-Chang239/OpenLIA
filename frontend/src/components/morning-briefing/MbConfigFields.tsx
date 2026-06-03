/**
 * MbConfigFields — the shared Morning Briefing config controls.
 *
 * The model / template / instructions / connectors / length / language /
 * reasoning controls, lifted out of ScheduleEditorModal so both the schedule
 * editor and the Run Now modal render the exact same settings. Owns the
 * template/instructions/data-source hooks and the upload sub-modals; the
 * parent owns the draft state and passes a patcher via `onChange`.
 *
 * Visual structure mirrors the ER (Equity Research v3) settings modal:
 * mono-eyebrow section headers, bordered section rhythm, card-list template /
 * instructions pickers, and Segmented controls for length / language /
 * reasoning. MB is purely template/instructions-driven — no ticker.
 */
import { useState, type ReactNode } from "react";
import { Trash2, Upload } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDataSource,
  MbInstructions,
  MbReasoningEffort,
  MbReportLength,
  MbTemplate,
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

/** Mono-eyebrow section label, matching the ER settings modal. */
export function MbSectionHeader({ label }: { label: string }) {
  return (
    <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
      {label}
    </span>
  );
}

interface SegOption<T extends string> {
  value: T;
  label: string;
}

/** Segmented radio control, matching the ER settings modal. */
export function MbSegmented<T extends string>({
  ariaLabel,
  value,
  options,
  onChange,
  testId,
}: {
  ariaLabel: string;
  value: T;
  options: readonly SegOption<T>[];
  onChange: (next: T) => void;
  testId?: string;
}) {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      data-testid={testId}
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
            aria-label={opt.value}
            data-testid={testId ? `${testId}-option-${opt.value}` : undefined}
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

/** Dashed mono "Upload" pill, matching the ER settings modal. */
function UploadPill({
  onClick,
  testId,
  label,
}: {
  onClick: () => void;
  testId: string;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      data-testid={testId}
      className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[3px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success] transition-colors"
    >
      <Upload size={11} strokeWidth={2} /> {label}
    </button>
  );
}

/** A single selectable card in the template / instructions picker lists. */
function OptionRow({
  active,
  onClick,
  testId,
  title,
  sublabel,
  onDelete,
  deleteAria,
}: {
  active: boolean;
  onClick: () => void;
  testId: string;
  title: string;
  sublabel?: string;
  onDelete?: () => void;
  deleteAria?: string;
}) {
  return (
    <div
      className={[
        "flex items-center gap-2 rounded-md border px-3 py-2",
        active
          ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
          : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
      ].join(" ")}
    >
      <button
        type="button"
        onClick={onClick}
        data-testid={testId}
        className="flex min-w-0 flex-1 flex-col text-left"
      >
        <span className="truncate text-[12.5px] font-medium text-[--color-text-primary]">
          {title}
        </span>
        {sublabel ? (
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            {sublabel}
          </span>
        ) : null}
      </button>
      {onDelete ? (
        <button
          type="button"
          aria-label={deleteAria}
          onClick={onDelete}
          className="rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover]"
        >
          <Trash2 size={12} />
        </button>
      ) : null}
    </div>
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

  const LENGTH_OPTIONS: readonly SegOption<MbReportLength>[] = LENGTH_IDS.map(
    (id) => ({
      value: id,
      label: t(`morning_briefing.schedule_editor.length_${id}`),
    }),
  );

  const LANGUAGE_OPTIONS: readonly SegOption<"en" | "zh-Hant">[] = [
    { value: "en", label: "English" },
    { value: "zh-Hant", label: "繁體中文" },
  ];

  const REASONING_OPTIONS: readonly SegOption<"default" | "medium" | "high">[] =
    [
      {
        value: "default",
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
  const reasoningValue: "default" | "medium" | "high" =
    draft.reasoning_effort ?? "default";

  const sortedTemplates = [...templates].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });
  const sortedInstructions = [...instructions].sort((a, b) => {
    if (a.is_builtin !== b.is_builtin) return a.is_builtin ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

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

  async function handleDeleteTemplate(tpl: MbTemplate) {
    if (tpl.is_builtin) return;
    await removeTemplate(tpl.id);
    if (draft.template_id === tpl.id) onChange({ template_id: "freeform" });
  }

  async function handleUploadInstructions(name: string, file: File) {
    const created = await uploadInstructions(name, file);
    onChange({ instructions_id: created.id });
    setInstructionsOpen(false);
  }

  async function handleDeleteInstructions(ins: MbInstructions) {
    if (ins.is_builtin) return;
    if (
      !window.confirm(
        t("morning_briefing.schedule_editor.instructions_delete_confirm"),
      )
    ) {
      return;
    }
    await removeInstructions(ins.id);
    if (draft.instructions_id === ins.id) onChange({ instructions_id: null });
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
    <div className="[&>section]:border-b [&>section]:border-[--color-border-subtle] [&>section]:py-5 [&>section:first-child]:pt-0 [&>section:last-child]:border-b-0 [&>section:last-child]:pb-0">
      {/* Model */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.model_title")}
        />
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
          {t("morning_briefing.schedule_editor.model_hint")}
        </p>
        <MbModelPicker
          onChange={handleModel}
          value={{ provider_kind: draft.provider_kind, model: draft.model }}
        />
      </section>

      {/* Template */}
      <section>
        <div className="mb-[10px] flex items-center justify-between">
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.template_title")}
          />
          <UploadPill
            onClick={() => setUploadOpen(true)}
            testId="mb-template-upload-open"
            label={t("morning_briefing.schedule_editor.template_upload")}
          />
        </div>
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
          {t("morning_briefing.schedule_editor.template_hint")}
        </p>
        <div data-testid="mb-template-select" className="flex flex-col gap-[4px]">
          <OptionRow
            active={draft.template_id === "freeform"}
            onClick={() => onChange({ template_id: "freeform" })}
            testId="mb-template-option-freeform"
            title={t("morning_briefing.schedule_editor.template_freeform")}
            sublabel={t(
              "morning_briefing.schedule_editor.template_freeform_sublabel",
            )}
          />
          {sortedTemplates.map((tpl) => (
            <OptionRow
              key={tpl.id}
              active={draft.template_id === tpl.id}
              onClick={() => onChange({ template_id: tpl.id })}
              testId={`mb-template-option-${tpl.id}`}
              title={tpl.name}
              sublabel={
                tpl.is_builtin
                  ? t("morning_briefing.schedule_editor.template_builtin")
                  : t("morning_briefing.schedule_editor.template_uploaded")
              }
              onDelete={
                tpl.is_builtin
                  ? undefined
                  : () => void handleDeleteTemplate(tpl)
              }
              deleteAria={t(
                "morning_briefing.schedule_editor.template_delete_aria",
              )}
            />
          ))}
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

      {/* Instructions */}
      <section>
        <div className="mb-[10px] flex items-center justify-between">
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.instructions_title")}
          />
          <UploadPill
            onClick={() => setInstructionsOpen(true)}
            testId="mb-instructions-upload-open"
            label={t("morning_briefing.schedule_editor.instructions_upload")}
          />
        </div>
        <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
          {t("morning_briefing.schedule_editor.instructions_hint")}
        </p>
        <div
          data-testid="mb-instructions-select"
          className="flex flex-col gap-[4px]"
        >
          <OptionRow
            active={draft.instructions_id === null}
            onClick={() => onChange({ instructions_id: null })}
            testId="mb-instructions-option-none"
            title={t("morning_briefing.schedule_editor.instructions_none")}
          />
          {sortedInstructions.map((ins) => (
            <OptionRow
              key={ins.id}
              active={draft.instructions_id === ins.id}
              onClick={() => onChange({ instructions_id: ins.id })}
              testId={`mb-instructions-option-${ins.id}`}
              title={ins.name}
              sublabel={
                ins.is_builtin
                  ? t("morning_briefing.schedule_editor.instructions_builtin")
                  : t("morning_briefing.schedule_editor.instructions_uploaded")
              }
              onDelete={
                ins.is_builtin
                  ? undefined
                  : () => void handleDeleteInstructions(ins)
              }
              deleteAria={t(
                "morning_briefing.schedule_editor.instructions_delete_aria",
              )}
            />
          ))}
        </div>
      </section>

      {/* Connectors */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.connectors_title")}
        />
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

      {/* Length */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.length_title")}
        />
        <MbSegmented
          ariaLabel={t("morning_briefing.schedule_editor.length_aria")}
          value={draft.length as MbReportLength}
          options={LENGTH_OPTIONS}
          onChange={(v) => onChange({ length: v })}
          testId="mb-length-select"
        />
      </section>

      {/* Language */}
      <section>
        <MbSectionHeader
          label={t("morning_briefing.schedule_editor.language_title")}
        />
        <MbSegmented
          ariaLabel={t("morning_briefing.schedule_editor.language_title")}
          value={draft.language as "en" | "zh-Hant"}
          options={LANGUAGE_OPTIONS}
          onChange={(v) => onChange({ language: v })}
          testId="mb-language-select"
        />
      </section>

      {/* Reasoning effort — Anthropic only */}
      {draft.provider_kind === "anthropic" ? (
        <section>
          <MbSectionHeader
            label={t("morning_briefing.schedule_editor.reasoning_title")}
          />
          <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-[10px]">
            {t("morning_briefing.schedule_editor.reasoning_hint")}
          </p>
          <MbSegmented
            ariaLabel={t("morning_briefing.schedule_editor.reasoning_title")}
            value={reasoningValue}
            options={REASONING_OPTIONS}
            onChange={(v) =>
              onChange({
                reasoning_effort: (v === "default"
                  ? null
                  : v) as MbReasoningEffort,
              })
            }
            testId="mb-reasoning-select"
          />
        </section>
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
    </div>
  );
}
