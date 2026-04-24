import { useState } from "react";

import {
  AddScheduleModal,
  type Day,
  type SchedulePayload,
} from "./AddScheduleModal";

// Component accepts either backend-style number days (0=Sun..6=Sat) or
// frontend-style string labels. Internally converts both directions at the
// edit boundary so the page can plug in either shape.
export type ScheduleDay = Day | number;

export interface ScheduleView {
  id: string;
  time: string;
  timezone: string;
  days_of_week: ScheduleDay[];
  label: string | null;
  is_enabled: boolean;
}

interface Props {
  schedules: ScheduleView[];
  onCreate: (p: SchedulePayload) => Promise<unknown>;
  onUpdate: (
    id: string,
    p: SchedulePayload & { is_enabled: boolean },
  ) => Promise<unknown>;
  onRemove: (id: string) => Promise<unknown>;
}

const DAY_BY_NUM: Record<number, Day> = {
  0: "sun",
  1: "mon",
  2: "tue",
  3: "wed",
  4: "thu",
  5: "fri",
  6: "sat",
};

function toStringDay(d: ScheduleDay): Day {
  return typeof d === "number" ? DAY_BY_NUM[d] : d;
}

function formatDays(days: ScheduleDay[]): string {
  return days
    .map(toStringDay)
    .map((d) => d[0].toUpperCase() + d.slice(1))
    .join(", ");
}

export function ScheduleManager({
  schedules,
  onCreate,
  onUpdate,
  onRemove,
}: Props) {
  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState<ScheduleView | null>(null);

  return (
    <section className="px-6 pt-5 pb-4">
      <header className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Scan Schedules
        </h3>
        <button
          type="button"
          onClick={() => setShowAdd(true)}
          className="border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] px-3 h-7 hover:border-[--color-border-primary]"
        >
          + Add Schedule
        </button>
      </header>
      {schedules.length === 0 ? (
        <div className="border border-dashed border-[--color-border-subtle] rounded-[--radius-md] py-6 text-center text-sm text-[--color-text-tertiary]">
          No scan schedules configured. Earnings reports will not be detected
          automatically.
        </div>
      ) : (
        <ul className="border border-[--color-border-subtle] rounded-[--radius-md] divide-y divide-[--color-border-subtle]">
          {schedules.map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between px-4 py-3"
            >
              <div className="text-sm">
                <span className="font-medium">{s.time}</span>{" "}
                <span className="text-[--color-text-secondary]">
                  {s.timezone}
                </span>
                {" — "}
                <span className="text-[--color-text-secondary]">
                  {formatDays(s.days_of_week)}
                </span>
                {s.label ? (
                  <span className="text-[--color-text-tertiary]">
                    {" "}— {s.label}
                  </span>
                ) : null}
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setEditing(s)}
                  className="text-sm text-[--color-accent-primary]"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => void onRemove(s.id)}
                  className="text-sm text-[--color-feedback-error]"
                >
                  Remove
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
      <AddScheduleModal
        open={showAdd}
        onClose={() => setShowAdd(false)}
        onSave={async (p) => {
          await onCreate(p);
        }}
      />
      {editing ? (
        <AddScheduleModal
          open
          onClose={() => setEditing(null)}
          initial={{
            time: editing.time,
            timezone: editing.timezone,
            days_of_week: editing.days_of_week.map(toStringDay),
            label: editing.label ?? "",
          }}
          onSave={async (p) => {
            await onUpdate(editing.id, { ...p, is_enabled: true });
          }}
        />
      ) : null}
    </section>
  );
}

