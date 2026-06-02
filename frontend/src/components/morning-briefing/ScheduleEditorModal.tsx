/**
 * ScheduleEditorModal — create or edit a Morning Briefing schedule.
 *
 * Each MB schedule binds its own config (template, instructions, data
 * connectors + web_search, model, language, length, reasoning) plus the
 * scheduling fields (time, timezone, days_of_week, label, is_enabled).
 * MB is purely template/instructions-driven — no ticker, no watchlist.
 *
 * Forks the EU ReportSettingsModal chrome (Radix dialog, scrollable body,
 * Save/Cancel footer) and layers the timing controls on top.
 */
import { useState, type ReactNode } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Trash2, X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDataSource,
  MbDayOfWeek,
  MbReasoningEffort,
  MbReportLength,
  MbSchedule,
  MbScheduleIn,
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

const DAY_NAMES: readonly MbDayOfWeek[] = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
];

const TIMEZONES = [
  "America/New_York",
  "America/Chicago",
  "America/Denver",
  "America/Los_Angeles",
  "Europe/London",
  "Europe/Paris",
  "Asia/Tokyo",
  "Asia/Shanghai",
  "Asia/Taipei",
  "UTC",
];

interface DraftState {
  time: string;
  timezone: string;
  days_of_week: MbDayOfWeek[];
  label: string;
  is_enabled: boolean;
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

function readProviderIds(raw: Record<string, unknown>): string[] {
  const ids = raw.provider_ids;
  return Array.isArray(ids) ? ids.map(String) : [];
}

function readWebSearch(raw: Record<string, unknown>): boolean {
  return raw.web_search === true;
}

function draftFromSchedule(schedule: MbSchedule): DraftState {
  return {
    time: schedule.time,
    timezone: schedule.timezone,
    days_of_week: schedule.days_of_week as MbDayOfWeek[],
    label: schedule.label,
    is_enabled: schedule.is_enabled,
    template_id: schedule.template_id ?? "freeform",
    instructions_id: schedule.instructions_id,
    provider_ids: readProviderIds(schedule.enabled_connectors),
    web_search:
      readWebSearch(schedule.enabled_connectors) || schedule.web_search,
    provider_kind: schedule.provider_kind,
    model: schedule.model,
    language: schedule.language,
    length: schedule.length,
    reasoning_effort: (schedule.reasoning_effort ?? null) as MbReasoningEffort,
  };
}

function freshDraft(): DraftState {
  return {
    time: "07:00",
    timezone: "America/New_York",
    days_of_week: ["mon", "tue", "wed", "thu", "fri"],
    label: "",
    is_enabled: true,
    template_id: "freeform",
    instructions_id: null,
    provider_ids: [],
    web_search: false,
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
  };
}

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
  /** When provided, the editor edits this schedule; otherwise creates. */
  schedule?: MbSchedule | null;
  onSave: (payload: MbScheduleIn) => Promise<unknown>;
  onClose: () => void;
}

export function ScheduleEditorModal({ schedule, onSave, onClose }: Props) {
  const { t } = useTranslation();
  const editing = Boolean(schedule);
  const [draft, setDraft] = useState<DraftState>(() =>
    schedule ? draftFromSchedule(schedule) : freshDraft(),
  );
  const [saving, setSaving] = useState(false);
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

  const bothEmpty = draft.template_id === "freeform" && !draft.instructions_id;
  const noDays = draft.days_of_week.length === 0;

  function handleModel(sel: MbModelSelection | null) {
    if (!sel) return;
    setDraft((d) => ({
      ...d,
      provider_kind: sel.provider_kind,
      model: sel.model,
    }));
  }

  async function handleUploadMarkdown(name: string, markdown: string) {
    const created = await createTemplate({ name, source_markdown: markdown });
    setDraft((d) => ({ ...d, template_id: created.id }));
    setUploadOpen(false);
  }

  async function handleUploadFile(name: string, file: File) {
    const created = await uploadTemplate(name, file);
    setDraft((d) => ({ ...d, template_id: created.id }));
    setUploadOpen(false);
  }

  async function handleDeleteTemplate() {
    if (!activeTemplate || activeTemplate.is_builtin) return;
    await removeTemplate(activeTemplate.id);
    setDraft((d) => ({ ...d, template_id: "freeform" }));
  }

  async function handleUploadInstructions(name: string, file: File) {
    const created = await uploadInstructions(name, file);
    setDraft((d) => ({ ...d, instructions_id: created.id }));
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
    setDraft((d) => ({ ...d, instructions_id: null }));
  }

  function toggleDay(d: MbDayOfWeek) {
    setDraft((prev) => ({
      ...prev,
      days_of_week: prev.days_of_week.includes(d)
        ? prev.days_of_week.filter((x) => x !== d)
        : [...prev.days_of_week, d],
    }));
  }

  async function handleSave() {
    setSaving(true);
    try {
      const payload: MbScheduleIn = {
        time: draft.time,
        timezone: draft.timezone,
        days_of_week: draft.days_of_week,
        label: draft.label,
        template_id: draft.template_id,
        instructions_id: draft.instructions_id,
        enabled_connectors: {
          provider_ids: draft.provider_ids,
          web_search: draft.web_search,
        },
        provider_kind: draft.provider_kind,
        model: draft.model,
        language: draft.language,
        length: draft.length,
        reasoning_effort: draft.reasoning_effort,
      };
      await onSave(payload);
      onClose();
    } finally {
      setSaving(false);
    }
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
      setDraft((d) => ({ ...d, web_search: !d.web_search }));
      return;
    }
    setDraft((d) => {
      const has = d.provider_ids.includes(s.key);
      return {
        ...d,
        provider_ids: has
          ? d.provider_ids.filter((k) => k !== s.key)
          : [...d.provider_ids, s.key],
      };
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
        <Toggle
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
    <Dialog.Root open onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 -translate-x-1/2 -translate-y-1/2 w-[560px] max-w-[92vw] max-h-[85vh] bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[12px] shadow-lg flex flex-col overflow-hidden">
          <header className="flex items-center justify-between px-5 h-12 border-b border-[--color-border-subtle] flex-shrink-0">
            <div>
              <Dialog.Title asChild>
                <h2 className="text-[15px] font-semibold text-[--color-text-primary] m-0">
                  {editing
                    ? t("morning_briefing.schedule_editor.edit_title")
                    : t("morning_briefing.schedule_editor.add_title")}
                </h2>
              </Dialog.Title>
              <Dialog.Description asChild>
                <p className="font-mono text-[10px] tracking-[0.12em] uppercase text-[--color-text-tertiary] m-0">
                  {t("morning_briefing.schedule_editor.subtitle")}
                </p>
              </Dialog.Description>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label={t("morning_briefing.schedule_editor.close_aria")}
                className="text-[--color-text-secondary] hover:text-[--color-text-primary] transition-colors"
              >
                <X size={16} />
              </button>
            </Dialog.Close>
          </header>

          <div className="flex-1 overflow-y-auto px-6 py-5">
            {/* Timing */}
            <section className="mb-7">
              {sectionTitle(t("morning_briefing.schedule_editor.timing_title"))}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("morning_briefing.schedule_editor.timing_hint")}
              </p>
              <div className="grid grid-cols-2 gap-3">
                <label className="flex flex-col gap-1.5">
                  <span className="text-[12px] text-[--color-text-tertiary]">
                    {t("morning_briefing.schedule_editor.time_label")}
                  </span>
                  <input
                    type="time"
                    value={draft.time}
                    aria-label={t("morning_briefing.schedule_editor.time_aria")}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, time: e.target.value }))
                    }
                    data-testid="mb-schedule-time"
                    className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-[12px] text-[--color-text-tertiary]">
                    {t("morning_briefing.schedule_editor.timezone_label")}
                  </span>
                  <select
                    value={draft.timezone}
                    aria-label={t(
                      "morning_briefing.schedule_editor.timezone_aria",
                    )}
                    onChange={(e) =>
                      setDraft((d) => ({ ...d, timezone: e.target.value }))
                    }
                    data-testid="mb-schedule-timezone"
                    className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
                  >
                    {TIMEZONES.map((tz) => (
                      <option key={tz} value={tz}>
                        {tz}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="mt-3">
                <span className="text-[12px] text-[--color-text-tertiary]">
                  {t("morning_briefing.schedule_editor.days_label")}
                </span>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {DAY_NAMES.map((d) => {
                    const on = draft.days_of_week.includes(d);
                    return (
                      <button
                        key={d}
                        type="button"
                        onClick={() => toggleDay(d)}
                        aria-pressed={on}
                        data-testid={`mb-schedule-day-${d}`}
                        className={[
                          "h-8 w-10 rounded-md text-[12px] font-medium transition-colors",
                          on
                            ? "bg-[--color-accent-primary] text-[--color-accent-on]"
                            : "border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]",
                        ].join(" ")}
                      >
                        {t(`morning_briefing.days.${d}`)}
                      </button>
                    );
                  })}
                </div>
                {noDays ? (
                  <p
                    data-testid="mb-schedule-no-days"
                    className="mt-2 text-[12px] text-[--color-feedback-danger]"
                  >
                    {t("morning_briefing.schedule_editor.days_select_one")}
                  </p>
                ) : null}
              </div>
              <label className="mt-3 flex flex-col gap-1.5">
                <span className="text-[12px] text-[--color-text-tertiary]">
                  {t("morning_briefing.schedule_editor.label_label")}
                </span>
                <input
                  type="text"
                  value={draft.label}
                  aria-label={t("morning_briefing.schedule_editor.label_aria")}
                  placeholder={t(
                    "morning_briefing.schedule_editor.label_placeholder",
                  )}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, label: e.target.value }))
                  }
                  maxLength={120}
                  data-testid="mb-schedule-label"
                  className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
                />
              </label>
              <div className="mt-3 border border-[--color-border-subtle] rounded-lg overflow-hidden">
                <Toggle
                  on={draft.is_enabled}
                  onClick={() =>
                    setDraft((d) => ({ ...d, is_enabled: !d.is_enabled }))
                  }
                  testId="mb-schedule-enabled"
                  label={t("morning_briefing.schedule_editor.enabled_label")}
                  ariaLabel={t("morning_briefing.schedule_editor.enabled_aria")}
                />
              </div>
            </section>

            <hr className="border-0 border-t border-[--color-border-subtle] my-7" />

            {/* Model */}
            <section className="mb-7">
              {sectionTitle(t("morning_briefing.schedule_editor.model_title"))}
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
              {sectionTitle(
                t("morning_briefing.schedule_editor.template_title"),
              )}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("morning_briefing.schedule_editor.template_hint")}
              </p>
              <div className="flex items-center gap-2">
                <select
                  value={draft.template_id}
                  onChange={(e) =>
                    setDraft((d) => ({ ...d, template_id: e.target.value }))
                  }
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
                        : t(
                            "morning_briefing.schedule_editor.template_custom_suffix",
                          )}
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
              {sectionTitle(
                t("morning_briefing.schedule_editor.instructions_title"),
              )}
              <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-3">
                {t("morning_briefing.schedule_editor.instructions_hint")}
              </p>
              <div className="flex items-center gap-2">
                <select
                  value={draft.instructions_id ?? ""}
                  onChange={(e) =>
                    setDraft((d) => ({
                      ...d,
                      instructions_id: e.target.value || null,
                    }))
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
              {sectionTitle(
                t("morning_briefing.schedule_editor.connectors_title"),
              )}
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
              {sectionTitle(t("morning_briefing.schedule_editor.length_title"))}
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
            <section
              className={draft.provider_kind === "anthropic" ? "mb-7" : "mb-2"}
            >
              {sectionTitle(
                t("morning_briefing.schedule_editor.language_title"),
              )}
              <select
                value={draft.language}
                onChange={(e) =>
                  setDraft((d) => ({ ...d, language: e.target.value }))
                }
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
                  {sectionTitle(
                    t("morning_briefing.schedule_editor.reasoning_title"),
                  )}
                  <p className="text-[13px] text-[--color-text-secondary] leading-[1.5] mb-2">
                    {t("morning_briefing.schedule_editor.reasoning_hint")}
                  </p>
                  <select
                    value={draft.reasoning_effort ?? ""}
                    onChange={(e) =>
                      setDraft((d) => ({
                        ...d,
                        reasoning_effort: (e.target.value ||
                          null) as MbReasoningEffort,
                      }))
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
          </div>

          <footer className="flex items-center justify-end gap-3 px-5 h-14 border-t border-[--color-border-subtle] flex-shrink-0">
            {bothEmpty ? (
              <p
                data-testid="mb-both-empty-error"
                className="mr-auto text-[12px] text-[--color-feedback-danger] leading-[1.4]"
              >
                {t("morning_briefing.schedule_editor.both_empty_error")}
              </p>
            ) : null}
            <button
              type="button"
              onClick={onClose}
              className="inline-flex items-center h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:border-[--color-border-strong] transition-colors text-[13px] font-medium"
            >
              {t("morning_briefing.schedule_editor.cancel")}
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              disabled={saving || bothEmpty || noDays}
              data-testid="mb-schedule-save"
              className="inline-flex items-center h-9 px-5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] disabled:opacity-50 transition-colors"
            >
              {saving
                ? t("morning_briefing.schedule_editor.saving")
                : t("morning_briefing.schedule_editor.save")}
            </button>
          </footer>
        </Dialog.Content>
      </Dialog.Portal>

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
    </Dialog.Root>
  );
}
