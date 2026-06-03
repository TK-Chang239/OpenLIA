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
import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type {
  MbDayOfWeek,
  MbReasoningEffort,
  MbSchedule,
  MbScheduleIn,
} from "../../api/morning-briefing";

import {
  MbConfigFields,
  MbToggle,
  isBriefEmpty,
  mbSectionTitle,
} from "./MbConfigFields";

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

  const bothEmpty = isBriefEmpty(draft);
  const noDays = draft.days_of_week.length === 0;

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
        is_enabled: draft.is_enabled,
      };
      await onSave(payload);
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
              {mbSectionTitle(t("morning_briefing.schedule_editor.timing_title"))}
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
                <MbToggle
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

            <MbConfigFields
              draft={draft}
              onChange={(patch) => setDraft((d) => ({ ...d, ...patch }))}
            />
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
    </Dialog.Root>
  );
}
