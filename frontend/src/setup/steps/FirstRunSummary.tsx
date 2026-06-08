import { useEffect, useState } from "react";
import { RotateCw } from "lucide-react";
import {
  fetchDeptHealth,
  recheckDeptHealth,
  type DepartmentHealth,
} from "../../api/dept-health";

export function FirstRunSummary() {
  const [healths, setHealths] = useState<DepartmentHealth[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [rechecking, setRechecking] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const list = await fetchDeptHealth();
        if (!cancelled) setHealths(list);
      } catch (err) {
        if (!cancelled)
          setError(err instanceof Error ? err.message : "Failed to load health.");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const onRecheck = async () => {
    setRechecking(true);
    setError(null);
    try {
      const list = await recheckDeptHealth();
      setHealths(list);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-check failed.");
    } finally {
      setRechecking(false);
    }
  };

  if (error) {
    return (
      <p role="alert" className="text-sm text-feedback-error">
        {error}
      </p>
    );
  }

  if (healths === null) {
    return <p className="text-sm text-text-secondary">Loading...</p>;
  }

  const active = healths.filter((h) => h.status === "active");
  const disabled = healths.filter((h) => h.status === "disabled");

  return (
    <section
      aria-label="Department status summary"
      className="space-y-3"
      data-testid="first-run-summary"
    >
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text-primary">
          Departments: {active.length} of {healths.length} active.
        </h3>
        <button
          type="button"
          onClick={onRecheck}
          disabled={rechecking}
          data-testid="dept-health-recheck"
          className="inline-flex items-center gap-1 rounded-md border border-border-secondary px-2 py-1 text-xs text-text-secondary hover:text-text-primary disabled:opacity-50"
        >
          <RotateCw size={12} className={rechecking ? "animate-spin" : ""} />
          {rechecking ? "Re-checking..." : "Re-check"}
        </button>
      </header>

      {active.length > 0 ? (
        <ul className="space-y-1">
          {active.map((h) => (
            <li
              key={h.department_id}
              className="flex items-center gap-2 text-sm text-text-primary"
            >
              <span className="rounded-full bg-feedback-success/10 px-2 py-0.5 text-xs font-medium text-feedback-success">
                Active
              </span>
              <span>{h.department_id}</span>
            </li>
          ))}
        </ul>
      ) : null}

      {disabled.length > 0 ? (
        <ul className="space-y-2">
          {disabled.map((h) => (
            <DisabledDeptRow key={h.department_id} health={h} />
          ))}
        </ul>
      ) : null}

      <p className="text-xs text-text-secondary">
        You can configure additional connectors anytime from Settings.
      </p>
    </section>
  );
}

function DisabledDeptRow({ health }: { health: DepartmentHealth }) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = health.missing_categories.length > 0;

  return (
    <li
      className="flex flex-col gap-1 text-sm text-text-primary"
      data-testid={`disabled-dept-${health.department_id}`}
    >
      <div className="flex items-start gap-2">
        <span className="rounded-full bg-feedback-warning/10 px-2 py-0.5 text-xs font-medium text-feedback-warning">
          Disabled
        </span>
        <span>
          {health.department_id}
          {health.reason ? (
            <span className="text-text-secondary"> — {health.reason}</span>
          ) : null}
        </span>
        {hasDetails ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            data-testid={`disabled-dept-${health.department_id}-toggle`}
            className="ml-auto text-xs text-accent-primary hover:underline"
          >
            {expanded ? "Hide details" : "Show details"}
          </button>
        ) : null}
      </div>

      {expanded && hasDetails ? (
        <div
          className="ml-7 rounded-md border border-border-subtle bg-bg-base px-3 py-2 text-xs text-text-secondary space-y-2"
          data-testid={`disabled-dept-${health.department_id}-details`}
        >
          {health.missing_categories.length > 0 ? (
            <div>
              <p className="font-medium text-text-primary">Missing categories</p>
              <ul className="ml-4 list-disc">
                {health.missing_categories.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
              <p className="mt-1">
                Add a connector in one of these categories on the Connectors
                step, then click Re-check.
              </p>
            </div>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}
