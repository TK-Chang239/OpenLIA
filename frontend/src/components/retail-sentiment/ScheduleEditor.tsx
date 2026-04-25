import { useState } from "react";

import type { RsSchedule, RsScheduleUpsert } from "../../api/retail-sentiment";

interface Props {
  open: boolean;
  schedule: RsSchedule | null;
  onClose: () => void;
  onSave: (payload: RsScheduleUpsert) => Promise<RsSchedule>;
}

const DAYS: Array<"mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"> = [
  "mon",
  "tue",
  "wed",
  "thu",
  "fri",
  "sat",
  "sun",
];

export function ScheduleEditor({ open, schedule, onClose, onSave }: Props) {
  const [time, setTime] = useState(schedule?.time ?? "08:00");
  const [tz, setTz] = useState(schedule?.timezone ?? "America/New_York");
  const [days, setDays] = useState<string[]>(
    schedule?.days_of_week ?? ["mon", "tue", "wed", "thu", "fri"],
  );
  const [label, setLabel] = useState(schedule?.label ?? "");
  const [enabled, setEnabled] = useState(schedule?.is_enabled ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await onSave({
        time,
        timezone: tz,
        days_of_week: days,
        label,
        is_enabled: enabled,
      });
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const toggleDay = (d: string) => {
    setDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  };

  return (
    <div
      role="dialog"
      aria-label="Schedule editor"
      data-testid="schedule-editor"
      className="fixed inset-0 z-40 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4 shadow-2xl">
        <h2 className="text-sm font-semibold">Retail Sentiment schedule</h2>
        <div className="mt-3 grid gap-3 text-sm">
          <label className="grid gap-1">
            Time
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
            />
          </label>
          <label className="grid gap-1">
            Timezone
            <input
              value={tz}
              onChange={(e) => setTz(e.target.value)}
              className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
            />
          </label>
          <div>
            <div className="mb-1 text-xs uppercase text-[--color-text-secondary]">
              Days
            </div>
            <div className="flex flex-wrap gap-1">
              {DAYS.map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => toggleDay(d)}
                  className={[
                    "rounded-full border px-2 py-1 text-xs",
                    days.includes(d)
                      ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                      : "border-[--color-border-subtle] bg-[--color-bg-input]",
                  ].join(" ")}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
          <label className="grid gap-1">
            Label
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1"
            />
          </label>
          <label className="inline-flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            Enabled
          </label>
        </div>
        {error ? (
          <div
            data-testid="schedule-error"
            className="mt-2 text-xs text-[--color-feedback-error]"
          >
            {error}
          </div>
        ) : null}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-[--color-border-secondary] px-3 py-1 text-xs"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={busy}
            className="rounded-md bg-[--color-accent-primary] px-3 py-1 text-xs text-[--color-accent-on] disabled:opacity-60"
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
