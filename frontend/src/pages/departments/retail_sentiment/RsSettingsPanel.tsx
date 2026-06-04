import { useEffect, useState } from "react";
import { fetchDeptHealth, type DepartmentHealth } from "../../../api/dept-health";
import {
  getSchedule,
  putSchedule,
  type RsSchedule,
  type RsScheduleUpsert,
} from "../../../api/retail-sentiment";
import { ScheduleEditor } from "../../../components/retail-sentiment/ScheduleEditor";

// ---------------------------------------------------------------------------
// Coverage constant
// ---------------------------------------------------------------------------

const RS_COVERAGE: Record<string, { label: string; satisfied: string; missing: string }> = {
  web_search: {
    label: "Web search",
    satisfied: "Retail Sentiment backbone active.",
    missing: "Required — without web search, Retail Sentiment cannot generate a reading.",
  },
  financial: {
    label: "Financial",
    satisfied:
      "Aggregated-sentiment crosscheck and analyst-gap tile active.",
    missing:
      "Optional — aggregated_sentiment and analyst_gap fields will be null without a financial connector. Add one in Settings, Connectors.",
  },
  news: {
    label: "News",
    satisfied: "Headline evidence list active.",
    missing:
      "Optional — evidence list falls back to web-search results without a news connector.",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RsSettingsPanel({
  onClose,
}: {
  onClose: () => void;
}): JSX.Element {
  const [coverage, setCoverage] = useState<DepartmentHealth | null>(null);
  const [schedule, setSchedule] = useState<RsSchedule | null>(null);
  const [scheduleVisible, setScheduleVisible] = useState(false);

  useEffect(() => {
    fetchDeptHealth()
      .then((rows) =>
        setCoverage(rows.find((r) => r.department_id === "retail_sentiment") ?? null),
      )
      .catch(() => setCoverage(null));
  }, []);

  useEffect(() => {
    getSchedule()
      .then((r) => setSchedule(r.schedule))
      .catch(() => setSchedule(null));
  }, []);

  const saveSchedule = async (payload: RsScheduleUpsert): Promise<RsSchedule> => {
    const updated = await putSchedule(payload);
    setSchedule(updated);
    return updated;
  };

  return (
    <div
      role="dialog"
      aria-label="Retail Sentiment settings"
      data-testid="rs-settings-panel"
      className="fixed inset-y-0 right-0 z-40 flex w-full max-w-md flex-col gap-6 overflow-y-auto border-l border-[--color-border-subtle] bg-[--color-bg-base] p-6 shadow-2xl"
    >
      <header className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-[--color-text-primary]">
          Retail Sentiment Settings
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

      {/* Coverage hint */}
      {coverage ? (
        <section className="space-y-3" data-testid="rs-coverage">
          <h3 className="text-sm font-medium text-[--color-text-primary]">
            Source coverage
          </h3>
          <ul className="space-y-2">
            {(["web_search", "financial", "news"] as const).map((cat) => {
              const note = RS_COVERAGE[cat];
              const satisfied = coverage.satisfied_categories?.includes(cat) ?? false;
              return (
                <li
                  key={cat}
                  data-testid={`rs-coverage-${cat}`}
                  className="text-xs text-[--color-text-secondary]"
                >
                  <span className="font-medium text-[--color-text-primary]">
                    {note.label}
                  </span>
                  {" — "}
                  <span
                    className={
                      satisfied
                        ? "text-[--color-feedback-success]"
                        : "text-[--color-text-secondary]"
                    }
                  >
                    {satisfied ? "active" : cat === "web_search" ? "required" : "not configured"}
                  </span>
                  {". "}
                  {satisfied ? note.satisfied : note.missing}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {/* Schedule */}
      <section className="space-y-3" data-testid="rs-settings-schedule-section">
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
          <ScheduleEditor
            open={scheduleVisible}
            schedule={schedule}
            onClose={() => setScheduleVisible(false)}
            onSave={saveSchedule}
          />
        ) : null}
      </section>

    </div>
  );
}
