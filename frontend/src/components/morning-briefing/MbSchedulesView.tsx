/**
 * MbSchedulesView — full-screen list of Morning Briefing schedules.
 *
 * Lists each schedule with its next fire time (via formatNextBriefing),
 * day-of-week chips, enabled state, and edit / delete affordances. "New
 * schedule" and per-row "Edit" open the ScheduleEditorModal (owned by the
 * parent page). Chrome mirrors the EU/ER overlay views.
 */
import { useState } from "react";
import { CalendarClock, ChevronLeft, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbDayOfWeek, MbSchedule } from "../../api/morning-briefing";
import { formatNextBriefing } from "../../lib/morning-briefing/next-briefing";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  schedules: MbSchedule[];
  onBack: () => void;
  onAdd: () => void;
  onEdit: (schedule: MbSchedule) => void;
  onRemove: (id: string) => Promise<void>;
}

const DAY_ORDER: readonly MbDayOfWeek[] = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
];

export function MbSchedulesView({
  schedules,
  onBack,
  onAdd,
  onEdit,
  onRemove,
}: Props) {
  const { t } = useTranslation();
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);

  return (
    <div
      className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto"
      data-testid="mb-schedules"
    >
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
        >
          <ChevronLeft size={14} /> {t("morning_briefing.schedules.back")}
        </button>
        <div className="flex flex-col items-center">
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {t("morning_briefing.schedules.eyebrow")}
          </span>
          <h2 className="text-[16px] font-semibold text-[--color-text-primary] m-0">
            {t("morning_briefing.schedules.title")}
          </h2>
        </div>
        <button
          type="button"
          onClick={onAdd}
          data-testid="mb-schedules-add"
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors"
        >
          <Plus size={13} /> {t("morning_briefing.schedules.add")}
        </button>
      </header>

      <div className="max-w-[800px] mx-auto px-4 sm:px-6 py-6">
        {schedules.length === 0 ? (
          <div
            data-testid="mb-schedules-empty"
            className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
          >
            <div
              aria-hidden="true"
              className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[--color-accent-primary] text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]"
            >
              <CalendarClock size={24} strokeWidth={1.6} />
            </div>
            <p className="text-[14px] text-[--color-text-secondary] max-w-[420px] m-0 mb-5 leading-[1.5]">
              {t("morning_briefing.schedules.empty")}
            </p>
            <button
              type="button"
              onClick={onAdd}
              data-testid="mb-schedules-empty-add"
              className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors"
            >
              <Plus size={14} /> {t("morning_briefing.schedules.add")}
            </button>
          </div>
        ) : (
          <ul className="flex flex-col gap-2">
            {schedules.map((s) => {
              const days = DAY_ORDER.filter((d) =>
                (s.days_of_week as MbDayOfWeek[]).includes(d),
              );
              return (
                <li
                  key={s.id}
                  data-testid="mb-schedule-row"
                  className="group relative flex items-center gap-3 overflow-hidden pl-5 pr-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-border-strong] hover:-translate-y-0.5 transition-[transform,border-color] duration-[--duration-normal]"
                >
                  <span
                    aria-hidden="true"
                    className={[
                      "absolute left-0 top-2 bottom-2 w-[3px] rounded-full",
                      s.is_enabled
                        ? "bg-[--color-accent-primary]"
                        : "bg-transparent",
                    ].join(" ")}
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-[14px] tabular-nums text-[--color-text-primary]">
                        {s.time}
                      </span>
                      {s.label ? (
                        <span className="text-[13px] text-[--color-text-secondary] truncate">
                          {s.label}
                        </span>
                      ) : null}
                      {s.is_enabled ? (
                        <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-feedback-success]">
                          <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
                          {t("morning_briefing.schedules.enabled_badge")}
                        </span>
                      ) : (
                        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary] border border-[--color-border-subtle] rounded px-1.5 py-px">
                          {t("morning_briefing.schedules.disabled_badge")}
                        </span>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1">
                      {days.map((d) => (
                        <span
                          key={d}
                          className="inline-flex items-center justify-center h-5 min-w-[28px] px-1 rounded font-mono text-[10px] uppercase tracking-[0.06em] text-[--color-text-secondary] bg-[--color-surface-hover]"
                        >
                          {t(`morning_briefing.days.${d}`)}
                        </span>
                      ))}
                    </div>
                    <p className="text-[12px] text-[--color-text-tertiary] m-0 mt-1.5">
                      {t("morning_briefing.schedules.next_run", {
                        when: formatNextBriefing(s),
                      })}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onEdit(s)}
                    data-testid={`mb-schedule-edit-${s.id}`}
                    className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] transition-colors"
                  >
                    <Pencil size={13} /> {t("morning_briefing.schedules.edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => setPendingRemoval(s.id)}
                    aria-label={t("morning_briefing.schedules.delete_aria")}
                    className="inline-flex h-8 w-8 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <ConfirmDialog
        open={pendingRemoval !== null}
        title={t("morning_briefing.schedules.remove_title")}
        description={t("morning_briefing.schedules.remove_description")}
        confirmLabel={t("morning_briefing.schedules.remove_confirm")}
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (id) void onRemove(id);
        }}
      />
    </div>
  );
}
