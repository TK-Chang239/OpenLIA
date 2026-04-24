import { useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
export type Day = (typeof DAYS)[number];

export interface SchedulePayload {
  time: string;
  timezone: string;
  days_of_week: Day[];
  label: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onSave: (payload: SchedulePayload) => Promise<void>;
  initial?: SchedulePayload;
}

export function AddScheduleModal({ open, onClose, onSave, initial }: Props) {
  const [time, setTime] = useState(initial?.time ?? "06:00");
  const [timezone, setTimezone] = useState(
    initial?.timezone ?? Intl.DateTimeFormat().resolvedOptions().timeZone,
  );
  const [days, setDays] = useState<Day[]>(initial?.days_of_week ?? []);
  const [label, setLabel] = useState(initial?.label ?? "");
  const [err, setErr] = useState<string | null>(null);

  function toggleDay(d: Day) {
    setDays((prev) =>
      prev.includes(d) ? prev.filter((x) => x !== d) : [...prev, d],
    );
  }

  async function handleSave() {
    if (days.length === 0) {
      setErr("Select at least one day");
      return;
    }
    setErr(null);
    await onSave({ time, timezone, days_of_week: days, label });
    onClose();
  }

  return (
    <Dialog.Root open={open} onOpenChange={(v) => (!v ? onClose() : null)}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40" />
        <Dialog.Content className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[420px] bg-[--color-bg-elevated] rounded-[--radius-lg] p-6 shadow-lg">
          <Dialog.Title className="text-lg font-semibold mb-4">
            {initial ? "Edit Schedule" : "Add Schedule"}
          </Dialog.Title>
          <label className="block text-sm mb-2">
            Time
            <input
              aria-label="time"
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm"
            />
          </label>
          <label className="block text-sm mb-2">
            Timezone
            <input
              aria-label="timezone"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm w-[200px]"
            />
          </label>
          <fieldset className="my-2">
            <legend className="text-sm">Days</legend>
            <div className="flex gap-2 flex-wrap">
              {DAYS.map((d) => (
                <label key={d} className="text-xs flex items-center gap-1">
                  <input
                    type="checkbox"
                    aria-label={d}
                    checked={days.includes(d)}
                    onChange={() => toggleDay(d)}
                  />
                  {d.toUpperCase()}
                </label>
              ))}
            </div>
          </fieldset>
          <label className="block text-sm mb-2">
            Label
            <input
              aria-label="label"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className="ml-2 bg-[--color-bg-base] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm w-[240px]"
            />
          </label>
          {err ? (
            <p className="text-xs text-[--color-feedback-error]">{err}</p>
          ) : null}
          <div className="flex justify-end gap-2 mt-4">
            <button
              type="button"
              onClick={onClose}
              className="text-sm text-[--color-text-secondary] px-3 h-8 rounded-[--radius-md]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void handleSave()}
              className="text-sm bg-[--color-accent-primary] text-white px-3 h-8 rounded-[--radius-md] hover:bg-[--color-accent-hover]"
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
