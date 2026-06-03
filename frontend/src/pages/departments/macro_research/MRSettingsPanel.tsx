import { useEffect, useState } from "react";
import {
  getConfig,
  putThresholdOverrides,
  runAssessment,
  type DashboardSummary,
} from "../../../api/macro_research";
import ScheduleEditor from "./ScheduleEditor";

// Dashboards the backend engine (report_dash_mr) can actually generate.
// There is no runtime endpoint exposing this set, so this is a hardcoded
// mirror of the engine's PAYLOAD_MODEL_BY_SLUG / implemented_dashboard_slugs().
// TODO: grow this list as backend dashboards are added (keep in sync with
// packages/core/.../report_dash_mr/tools/dashboard_tools.py).
const IMPLEMENTED_DASHBOARDS = [
  "debt_cycle",
  "world_order",
  "four_seasons",
  "all_weather",
  "five_forces",
  "summary",
];

interface ThresholdRow {
  key: string;
  value: string;
}

function rowsFromOverrides(
  overrides: Record<string, unknown> | null | undefined,
): ThresholdRow[] {
  if (!overrides) return [];
  return Object.entries(overrides).map(([key, value]) => ({
    key,
    value: typeof value === "string" ? value : JSON.stringify(value),
  }));
}

function rowsToOverrides(rows: ThresholdRow[]): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const r of rows) {
    if (!r.key.trim()) continue;
    const trimmed = r.value.trim();
    const numeric = Number(trimmed);
    if (trimmed !== "" && !Number.isNaN(numeric)) {
      out[r.key] = numeric;
    } else if (trimmed === "true" || trimmed === "false") {
      out[r.key] = trimmed === "true";
    } else {
      out[r.key] = trimmed;
    }
  }
  return out;
}

export default function MRSettingsPanel({
  dashboards,
  onClose,
}: {
  dashboards: DashboardSummary[];
  onClose: () => void;
}): JSX.Element {
  const initialSlug = dashboards[0]?.slug ?? "";
  const [activeSlug, setActiveSlug] = useState(initialSlug);
  const [rows, setRows] = useState<ThresholdRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scheduleVisible, setScheduleVisible] = useState(true);
  const [running, setRunning] = useState<string | null>(null);

  const onRunNow = async (slug: string) => {
    setRunning(slug);
    try {
      await runAssessment(slug);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(null);
    }
  };

  useEffect(() => {
    if (!activeSlug) return;
    getConfig(activeSlug)
      .then((cfg) => setRows(rowsFromOverrides(cfg.threshold_overrides)))
      .catch((e: unknown) => setError(String(e)));
  }, [activeSlug]);

  const onAddRow = () => setRows([...rows, { key: "", value: "" }]);
  const onChangeRow = (idx: number, patch: Partial<ThresholdRow>) =>
    setRows(rows.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  const onRemoveRow = (idx: number) => setRows(rows.filter((_, i) => i !== idx));

  const onSaveThresholds = async () => {
    setSaving(true);
    setError(null);
    try {
      const overrides = rowsToOverrides(rows);
      await putThresholdOverrides(activeSlug, overrides);
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-label="Macro Research settings"
      data-testid="mr-settings-panel"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col gap-6 overflow-y-auto border-l border-[--color-border-subtle] bg-[--color-bg-base] p-6 shadow-2xl"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[--color-text-primary]">
          Macro Research Settings
        </h2>
        <button
          type="button"
          aria-label="Close settings"
          onClick={onClose}
          className="rounded-[--radius-md] px-2 py-1 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          Close
        </button>
      </header>

      <section className="space-y-3" data-testid="mr-settings-runnow-section">
        <h3 className="text-sm font-medium text-[--color-text-primary]">
          Run assessment now
        </h3>
        <div className="flex flex-wrap gap-2">
          {dashboards
            .filter((d) => IMPLEMENTED_DASHBOARDS.includes(d.slug))
            .map((d) => (
              <button
                key={d.slug}
                type="button"
                data-testid={`mr-runnow-${d.slug}`}
                disabled={running === d.slug}
                onClick={() => onRunNow(d.slug)}
                className="inline-flex items-center gap-1.5 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1.5 text-xs text-[--color-text-primary] hover:border-[--color-feedback-success] disabled:opacity-60"
              >
                {running === d.slug ? "Running…" : d.display_name}
              </button>
            ))}
        </div>
      </section>

      <section
        className="space-y-3"
        data-testid="mr-settings-schedule-section"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-[--color-text-primary]">
            Assessment Schedule
          </h3>
          <button
            type="button"
            onClick={() => setScheduleVisible((v) => !v)}
            className="text-xs text-[--color-text-secondary] hover:text-[--color-text-primary]"
          >
            {scheduleVisible ? "Hide" : "Edit"}
          </button>
        </div>
        {scheduleVisible ? (
          <ScheduleEditor onClose={() => setScheduleVisible(false)} />
        ) : null}
      </section>

      <section
        className="space-y-3"
        data-testid="mr-settings-threshold-section"
      >
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-[--color-text-primary]">
            Threshold Overrides
          </h3>
          <select
            aria-label="Dashboard"
            value={activeSlug}
            onChange={(e) => setActiveSlug(e.target.value)}
            className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 text-sm text-[--color-text-primary]"
          >
            {dashboards.map((d) => (
              <option key={d.slug} value={d.slug}>
                {d.display_name}
              </option>
            ))}
          </select>
        </div>

        <ul className="space-y-2">
          {rows.length === 0 ? (
            <li className="text-xs text-[--color-text-tertiary]">
              No overrides set.
            </li>
          ) : null}
          {rows.map((row, idx) => (
            <li key={idx} className="flex gap-2">
              <input
                aria-label={`override-${idx}-key`}
                value={row.key}
                onChange={(e) => onChangeRow(idx, { key: e.target.value })}
                placeholder="key"
                className="w-1/2 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 text-sm text-[--color-text-primary]"
              />
              <input
                aria-label={`override-${idx}-value`}
                value={row.value}
                onChange={(e) => onChangeRow(idx, { value: e.target.value })}
                placeholder="value"
                className="w-1/2 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 text-sm text-[--color-text-primary]"
              />
              <button
                type="button"
                aria-label={`remove-override-${idx}`}
                onClick={() => onRemoveRow(idx)}
                className="rounded-[--radius-md] border border-[--color-border-subtle] px-2 text-xs text-[--color-text-secondary]"
              >
                ×
              </button>
            </li>
          ))}
        </ul>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAddRow}
            className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1 text-xs text-[--color-text-primary]"
          >
            Add override
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={onSaveThresholds}
            className="rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-accent-primary] px-3 py-1 text-xs text-[--color-text-on-accent] disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save thresholds"}
          </button>
        </div>

        {error ? (
          <div role="alert" className="text-xs text-[--color-feedback-error]">
            {error}
          </div>
        ) : null}
      </section>
    </div>
  );
}
