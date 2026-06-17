import { useEffect, useState } from "react";
import { runAssessment, type DashboardSummary } from "../../../api/macro_research";
import { fetchDeptHealth, type DepartmentHealth } from "../../../api/dept-health";

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

const MR_COVERAGE: Record<string, { label: string; satisfied: string; missing: string }> = {
  web_search: {
    label: "Web search",
    satisfied: "Macro backbone active.",
    missing: "Required — without it Macro Research is disabled.",
  },
  financial: {
    label: "Financial",
    satisfied: "Live quotes and indicators active.",
    missing:
      "Optional — quote/indicator tiles fall back to web search or show source-unavailable. Add one in Settings, Connectors.",
  },
  news: {
    label: "News",
    satisfied: "Headlines active.",
    missing: "Optional — narrative-context tiles fall back to web search.",
  },
};

export default function MRSettingsPanel({
  dashboards,
  onClose,
}: {
  dashboards: DashboardSummary[];
  onClose: () => void;
}): JSX.Element {
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [coverage, setCoverage] = useState<DepartmentHealth | null>(null);

  const onRunNow = async (slug: string) => {
    setRunning(slug);
    setError(null);
    try {
      await runAssessment(slug);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(null);
    }
  };

  useEffect(() => {
    fetchDeptHealth()
      .then((rows) =>
        setCoverage(rows.find((r) => r.department_id === "macro_research") ?? null),
      )
      .catch(() => setCoverage(null));
  }, []);

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
        <p className="text-xs text-[--color-text-tertiary]">
          Regenerate a single dashboard immediately. The refresh cadence is set
          from the header control.
        </p>
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
        {error ? (
          <div role="alert" className="text-xs text-[--color-feedback-error]">
            {error}
          </div>
        ) : null}
      </section>

      {coverage ? (
        <section className="space-y-3" data-testid="mr-coverage">
          <h3 className="text-sm font-medium text-[--color-text-primary]">Source coverage</h3>
          <ul className="space-y-2">
            {(["web_search", "financial", "news"] as const).map((cat) => {
              const note = MR_COVERAGE[cat];
              const satisfied = coverage.satisfied_categories?.includes(cat) ?? false;
              return (
                <li
                  key={cat}
                  data-testid={`mr-coverage-${cat}`}
                  className="text-xs text-[--color-text-secondary]"
                >
                  <span className="font-medium text-[--color-text-primary]">{note.label}</span>
                  {" — "}
                  <span
                    className={
                      satisfied
                        ? "text-[--color-feedback-success]"
                        : "text-[--color-text-secondary]"
                    }
                  >
                    {satisfied ? "active" : "not configured"}
                  </span>
                  {". "}
                  {satisfied ? note.satisfied : note.missing}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
