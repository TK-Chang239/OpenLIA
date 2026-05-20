import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbSchedule } from "../../api/morning-briefing";

interface Props {
  schedule: MbSchedule;
  onEdit: () => void;
  onDelete: () => void;
}

function formatDays(
  days: string[],
  t: (key: string) => string,
): string {
  if (days.length === 0) return "—";
  const lower = days.map((d) => d.toLowerCase());
  const mf = ["mon", "tue", "wed", "thu", "fri"];
  if (lower.length === 5 && mf.every((d) => lower.includes(d))) {
    return t("morning_briefing.schedule_row.mon_fri");
  }
  if (lower.length === 7) return t("morning_briefing.schedule_row.every_day");
  return days
    .map((d) => d.charAt(0).toUpperCase() + d.slice(1, 3).toLowerCase())
    .join(", ");
}

export function ScheduleRow({ schedule, onEdit, onDelete }: Props) {
  const { t } = useTranslation();
  const isPost = /post/i.test(schedule.label);
  const labelTone = isPost
    ? {
        color: "var(--color-feedback-warning)",
        background: "rgba(220,150,20,0.1)",
      }
    : {
        color: "var(--color-feedback-success)",
        background: "rgba(107,130,0,0.1)",
      };
  return (
    <div
      className="flex items-center gap-3.5 px-5 py-3.5 border-b last:border-b-0"
      style={{ borderColor: "var(--color-border-subtle)" }}
      data-testid={`schedule-row-${schedule.id}`}
    >
      <div className="font-mono text-[16px] font-medium text-[--color-text-primary] tabular-nums min-w-[110px]">
        {schedule.time}
      </div>
      <div className="flex-1 min-w-0 text-[13.5px] text-[--color-text-secondary]">
        <span>{formatDays(schedule.days_of_week, t)}</span>
        <span className="text-[--color-text-tertiary]"> · {schedule.timezone}</span>
        {schedule.label ? (
          <span
            className="ml-2 inline-flex font-mono text-[9.5px] tracking-[0.1em] uppercase px-2 py-0.5 rounded"
            style={labelTone}
          >
            {schedule.label}
          </span>
        ) : null}
      </div>
      <div className="flex gap-1">
        <button
          type="button"
          onClick={onEdit}
          className="inline-flex items-center h-7 px-3 rounded-md text-[13px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
          data-testid={`schedule-row-edit-${schedule.id}`}
        >
          {t("morning_briefing.schedule_row.edit")}
        </button>
        <button
          type="button"
          onClick={onDelete}
          aria-label={t("morning_briefing.schedule_row.delete_aria")}
          className="inline-flex items-center justify-center h-7 w-7 rounded-md text-[--color-feedback-error] hover:bg-[rgba(224,92,48,0.08)]"
          data-testid={`schedule-row-delete-${schedule.id}`}
        >
          <X size={14} strokeWidth={1.8} />
        </button>
      </div>
    </div>
  );
}
