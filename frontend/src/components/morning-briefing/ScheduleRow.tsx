import type { MbSchedule } from "../../api/morning-briefing";

interface Props {
  schedule: MbSchedule;
  onEdit: () => void;
  onDelete: () => void;
}

export function ScheduleRow({ schedule, onEdit, onDelete }: Props) {
  const days = schedule.days_of_week.join(", ");
  return (
    <div
      className="flex items-center gap-3 rounded-[var(--radius-lg,0.5rem)] border px-3 py-2 text-sm"
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-base)",
      }}
      data-testid={`schedule-row-${schedule.id}`}
    >
      <div className="flex-1 min-w-0 truncate">
        <span className="font-medium">{schedule.time}</span>
        <span style={{ color: "var(--color-text-tertiary)" }}>
          {` · ${schedule.timezone} · ${days}`}
        </span>
        {schedule.label && (
          <span className="ml-2" style={{ color: "var(--color-text-tertiary)" }}>
            {`— ${schedule.label}`}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onEdit}
        className="text-xs underline"
        data-testid={`schedule-row-edit-${schedule.id}`}
      >
        Edit
      </button>
      <button
        type="button"
        onClick={onDelete}
        aria-label="Delete schedule"
        className="text-xs"
        style={{ color: "var(--color-text-tertiary)" }}
        data-testid={`schedule-row-delete-${schedule.id}`}
      >
        {"×"}
      </button>
    </div>
  );
}
