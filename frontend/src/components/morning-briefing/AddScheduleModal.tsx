import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";

import type { MbScheduleUpsert } from "../../api/morning-briefing";

const DAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;

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

interface Props {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: MbScheduleUpsert) => void;
  initial?: MbScheduleUpsert;
}

export function AddScheduleModal({
  open,
  onClose,
  onSubmit,
  initial,
}: Props) {
  const [time, setTime] = useState(initial?.time ?? "07:00");
  const [timezone, setTimezone] = useState(
    initial?.timezone ?? "America/New_York",
  );
  const [days, setDays] = useState<string[]>(
    initial?.days_of_week ?? ["mon", "tue", "wed", "thu", "fri"],
  );
  const [label, setLabel] = useState(initial?.label ?? "");

  useEffect(() => {
    if (open) {
      setTime(initial?.time ?? "07:00");
      setTimezone(initial?.timezone ?? "America/New_York");
      setDays(initial?.days_of_week ?? ["mon", "tue", "wed", "thu", "fri"]);
      setLabel(initial?.label ?? "");
    }
  }, [open, initial]);

  const toggleDay = (d: string) => {
    setDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  };

  const submit = () => {
    onSubmit({ time, timezone, days_of_week: days, label });
  };

  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay
          className="fixed inset-0 z-40"
          style={{ background: "rgba(0,0,0,0.4)" }}
        />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-[var(--radius-lg,0.5rem)] border p-4 w-[420px] z-50 space-y-3"
          style={{
            borderColor: "var(--color-border-subtle)",
            background: "var(--color-bg-base)",
          }}
          data-testid="add-schedule-modal"
        >
          <Dialog.Title className="text-base font-semibold">
            {initial ? "Edit schedule" : "Add schedule"}
          </Dialog.Title>
          <Dialog.Description className="sr-only">
            Configure time, timezone, days, and label for this Morning Briefing
            schedule.
          </Dialog.Description>
          <div className="space-y-2 text-sm">
            <label className="block">
              <span className="text-xs">Time</span>
              <input
                type="time"
                className="block w-full rounded border px-2 py-1"
                style={{ borderColor: "var(--color-border-subtle)" }}
                value={time}
                onChange={(e) => setTime(e.target.value)}
                data-testid="add-schedule-time"
              />
            </label>
            <label className="block">
              <span className="text-xs">Timezone</span>
              <select
                className="block w-full rounded border px-2 py-1"
                style={{ borderColor: "var(--color-border-subtle)" }}
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                data-testid="add-schedule-tz"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
              </select>
            </label>
            <div>
              <span className="text-xs">Days</span>
              <div className="flex gap-1 flex-wrap mt-1">
                {DAY_NAMES.map((d) => {
                  const pressed = days.includes(d);
                  return (
                    <button
                      type="button"
                      key={d}
                      aria-pressed={pressed}
                      onClick={() => toggleDay(d)}
                      data-testid={`add-schedule-day-${d}`}
                      className="px-2 py-1 rounded border text-xs"
                      style={{
                        borderColor: "var(--color-border-subtle)",
                        background: pressed
                          ? "var(--color-accent-primary)"
                          : "transparent",
                        color: pressed
                          ? "var(--color-accent-on)"
                          : "inherit",
                      }}
                    >
                      {d}
                    </button>
                  );
                })}
              </div>
            </div>
            <label className="block">
              <span className="text-xs">Label</span>
              <input
                className="block w-full rounded border px-2 py-1"
                style={{ borderColor: "var(--color-border-subtle)" }}
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Pre-Market"
                data-testid="add-schedule-label"
              />
            </label>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1 rounded border text-sm"
              style={{ borderColor: "var(--color-border-subtle)" }}
              data-testid="add-schedule-cancel"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submit}
              className="px-3 py-1 rounded text-sm"
              style={{
                background: "var(--color-accent-primary)",
                color: "var(--color-accent-on)",
              }}
              data-testid="add-schedule-submit"
            >
              {initial ? "Update Schedule" : "Add Schedule"}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
