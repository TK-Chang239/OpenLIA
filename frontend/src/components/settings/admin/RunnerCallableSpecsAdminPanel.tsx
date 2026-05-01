/**
 * Admin panel: view resolved runner_callable_specs grouped by department,
 * with a per-row "Re-resolve" button that re-runs the proposed-specs
 * resolver for the owning connector.
 */
import { useEffect, useMemo, useState } from "react";
import {
  listRunnerSpecs,
  type RunnerSpecRow,
} from "../../../api/runner_specs";
import { reResolveSpecs } from "../../../api/connectors";

export function RunnerCallableSpecsAdminPanel(): JSX.Element {
  const [rows, setRows] = useState<RunnerSpecRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listRunnerSpecs();
      setRows(r);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load specs.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const grouped = useMemo(() => {
    const map: Record<string, RunnerSpecRow[]> = {};
    for (const r of rows) {
      (map[r.department_id] ??= []).push(r);
    }
    return map;
  }, [rows]);

  const onReResolve = async (row: RunnerSpecRow) => {
    setBusy(row.id);
    try {
      await reResolveSpecs(row.connector_id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-resolve failed.");
    } finally {
      setBusy(null);
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">
          Resolved callable specs
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Per-department, per-need callable bindings persisted by the wizard
          adapter. Re-resolve to refresh from the connector's current
          inventory.
        </p>
      </header>

      {error ? (
        <p role="alert" className="text-sm text-feedback-error">
          {error}
        </p>
      ) : null}

      {Object.keys(grouped).length === 0 ? (
        <p className="text-sm text-text-secondary">
          No resolved specs yet. Approve a proposal in the wizard or
          connector settings.
        </p>
      ) : null}

      {Object.entries(grouped).map(([deptId, deptRows]) => (
        <section
          key={deptId}
          aria-label={`Specs for ${deptId}`}
          className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3"
        >
          <h3 className="text-sm font-medium text-text-primary">{deptId}</h3>
          <ul className="space-y-3">
            {deptRows.map((r) => (
              <li
                key={r.id}
                data-testid={`runner-spec-${r.id}`}
                className="rounded-md border border-border-subtle bg-bg-base p-3"
              >
                <header className="flex items-baseline justify-between gap-3">
                  <div>
                    <p className="text-sm text-text-primary">
                      need: {r.need_id}{" "}
                      <span className="text-xs text-text-secondary">
                        ({r.access_mode})
                      </span>
                    </p>
                    <p className="text-xs text-text-secondary font-mono">
                      connector: {r.connector_id}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onReResolve(r)}
                    disabled={busy === r.id}
                    className="text-xs text-accent-primary hover:underline disabled:opacity-50"
                  >
                    {busy === r.id ? "Re-resolving..." : "Re-resolve"}
                  </button>
                </header>
                <pre className="mt-2 overflow-auto rounded-md border border-border-subtle bg-bg-elevated p-2 font-mono text-xs text-text-primary">
                  {JSON.stringify(r.spec, null, 2)}
                </pre>
                {r.canary_value ? (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-text-secondary">
                      Canary value
                    </summary>
                    <pre className="mt-1 overflow-auto rounded-md border border-border-subtle bg-bg-elevated p-2 font-mono">
                      {JSON.stringify(r.canary_value, null, 2)}
                    </pre>
                  </details>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
