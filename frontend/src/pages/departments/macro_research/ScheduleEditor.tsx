import { useEffect, useState } from "react";
import {
  deleteSchedule,
  getSchedule,
  putSchedule,
  type ScheduleState,
} from "../../../api/macro_research";

const PRESETS: { label: string; cron: string }[] = [
  { label: "Weekly (Sun 00:00)", cron: "0 0 * * 0" },
  { label: "Quarterly (1st of month, every 3 mo)", cron: "0 0 1 */3 *" },
];

export default function ScheduleEditor({
  onClose,
}: {
  onClose: () => void;
}): JSX.Element {
  const [state, setState] = useState<ScheduleState | null>(null);
  const [cron, setCron] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSchedule()
      .then((s) => {
        setState(s);
        setCron(s.cron_expression ?? "");
      })
      .catch((e: unknown) => setError(String(e)));
  }, []);

  const onSave = async () => {
    if (!cron.trim()) {
      setError("Cron expression cannot be empty");
      return;
    }
    setSaving(true);
    try {
      const next = await putSchedule(cron.trim());
      setState(next);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  const onClear = async () => {
    setSaving(true);
    try {
      await deleteSchedule();
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Macro Research schedule"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] p-5 shadow-lg">
        <header className="mb-3 flex items-baseline justify-between">
          <h3 className="text-lg font-semibold text-[--color-text-primary]">
            Assessment Schedule
          </h3>
          {state?.last_assessment_at ? (
            <span className="text-xs text-[--color-text-tertiary]">
              Last: {new Date(state.last_assessment_at).toLocaleString()}
            </span>
          ) : null}
        </header>
        <div className="space-y-3">
          <label className="block text-sm">
            <span className="text-[--color-text-secondary]">
              Cron expression
            </span>
            <input
              type="text"
              value={cron}
              onChange={(e) => setCron(e.target.value)}
              placeholder="0 0 * * 0"
              className="mt-1 w-full rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 font-mono text-sm text-[--color-text-primary]"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.cron}
                type="button"
                onClick={() => setCron(p.cron)}
                className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-base] px-2.5 py-1 text-xs text-[--color-text-primary] hover:border-[--color-accent-primary]"
              >
                {p.label}
              </button>
            ))}
          </div>
          {error ? (
            <div className="text-sm text-[--color-feedback-error]">{error}</div>
          ) : null}
        </div>
        <footer className="mt-5 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={onClear}
            disabled={saving || !state?.cron_expression}
            className="text-sm text-[--color-text-tertiary] hover:text-[--color-feedback-error] disabled:opacity-40"
          >
            Clear schedule
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-1.5 text-sm text-[--color-text-primary]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onSave}
              disabled={saving}
              className="rounded-[--radius-md] bg-[--color-accent-primary] px-3 py-1.5 text-sm font-medium text-black disabled:opacity-60"
            >
              {saving ? "Saving…" : "Save"}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
