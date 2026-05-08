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

const FIELD_INPUT =
  "h-8 px-2.5 rounded-md border bg-[--color-bg-input] text-[12.5px] focus:outline-none focus:border-[--color-accent-primary]";

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
      <div
        className="w-full max-w-md rounded-md border shadow-2xl"
        style={{
          background: "var(--color-bg-elevated)",
          borderColor: "var(--color-border-subtle)",
        }}
      >
        <header
          className="flex items-center justify-between px-5"
          style={{
            height: 52,
            borderBottom: "1px solid var(--color-border-subtle)",
          }}
        >
          <span
            className="font-mono"
            style={{
              fontSize: 10,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--color-text-tertiary)",
            }}
          >
            Schedule · Retail Sentiment
          </span>
        </header>
        <div className="p-5 space-y-3 text-[13px]">
          <label className="grid gap-1">
            <span className="rs-mono-label">Time</span>
            <input
              type="time"
              value={time}
              onChange={(e) => setTime(e.target.value)}
              className={FIELD_INPUT}
              style={{ borderColor: "var(--color-border-secondary)" }}
            />
          </label>
          <label className="grid gap-1">
            <span className="rs-mono-label">Timezone</span>
            <input
              value={tz}
              onChange={(e) => setTz(e.target.value)}
              className={FIELD_INPUT}
              style={{ borderColor: "var(--color-border-secondary)" }}
            />
          </label>
          <div>
            <span className="rs-mono-label block mb-1.5">Days</span>
            <div className="flex flex-wrap gap-1.5">
              {DAYS.map((d) => {
                const on = days.includes(d);
                return (
                  <button
                    key={d}
                    type="button"
                    onClick={() => toggleDay(d)}
                    className={[
                      "inline-flex items-center h-7 px-3 rounded-full border text-[11px] uppercase tracking-[0.1em] font-mono",
                      on
                        ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                        : "border-[--color-border-subtle] bg-[--color-bg-input] text-[--color-text-secondary]",
                    ].join(" ")}
                  >
                    {d}
                  </button>
                );
              })}
            </div>
          </div>
          <label className="grid gap-1">
            <span className="rs-mono-label">Label</span>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              className={FIELD_INPUT}
              style={{ borderColor: "var(--color-border-secondary)" }}
            />
          </label>
          <label className="inline-flex items-center gap-2 text-[12px]">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
            />
            <span className="rs-mono-label" style={{ color: "var(--color-text-primary)" }}>
              Enabled
            </span>
          </label>
          {error ? (
            <div
              data-testid="schedule-error"
              className="text-[11px]"
              style={{ color: "var(--color-feedback-error)" }}
            >
              {error}
            </div>
          ) : null}
        </div>
        <footer
          className="px-5 py-3 flex items-center justify-end gap-2"
          style={{ borderTop: "1px solid var(--color-border-subtle)" }}
        >
          <button
            type="button"
            onClick={onClose}
            className="inline-flex items-center h-8 px-3 rounded-md border text-[12px]"
            style={{
              borderColor: "var(--color-border-secondary)",
              color: "var(--color-text-secondary)",
            }}
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => void submit()}
            disabled={busy}
            className="inline-flex items-center h-8 px-3 rounded-md text-[12px] font-medium disabled:opacity-60"
            style={{
              background: "var(--color-accent-primary)",
              color: "var(--color-accent-on)",
            }}
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </footer>
      </div>
    </div>
  );
}
