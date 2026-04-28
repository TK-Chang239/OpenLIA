import { useEffect, useState } from "react";
import {
  fetchDeptHealth,
  type DepartmentHealth,
} from "../../api/dept-health";

export function FirstRunSummary() {
  const [healths, setHealths] = useState<DepartmentHealth[] | null>(null);
  const [error, setError] = useState<string | null>(null);

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
      <header>
        <h3 className="text-sm font-medium text-text-primary">
          Departments: {active.length} of {healths.length} active.
        </h3>
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
        <ul className="space-y-1">
          {disabled.map((h) => (
            <li
              key={h.department_id}
              className="flex items-start gap-2 text-sm text-text-primary"
            >
              <span className="rounded-full bg-feedback-warning/10 px-2 py-0.5 text-xs font-medium text-feedback-warning">
                Disabled
              </span>
              <span>
                {h.department_id}
                {h.reason ? (
                  <span className="text-text-secondary"> — {h.reason}</span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="text-xs text-text-secondary">
        You can configure additional connectors anytime from Settings.
      </p>
    </section>
  );
}
