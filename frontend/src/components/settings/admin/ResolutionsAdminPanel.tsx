/**
 * Phase 9: post-wizard admin panel for runner-spec resolutions.
 *
 * Mounts the same `ResolveRow` components from the wizard so the user
 * can edit any persisted spec long after install. Each Edit drops the
 * spec to a draft until smoke passes; failures preserve the previous
 * spec and surface a typed failure panel.
 *
 * Per-spec history is fetched from `/api/runner-specs/{id}/history`
 * (Phase 10) and rendered inline.
 */
import { useEffect, useMemo, useState } from "react";
import { ResolveRow, type ResolveRowNeed } from "../../../setup/steps/ResolveRow";
import {
  getSpecHistory,
  listRunnerSpecs,
  type HistoryEntry,
  type RunnerSpecRow,
} from "../../../api/runner_specs";
import { listConnectors, type ConnectorRow } from "../../../api/connectors";

interface NeedFromConfig {
  department_id: string;
  need_id: string;
  description: string;
  shape: string;
}

const KNOWN_NEEDS: NeedFromConfig[] = [
  // Minimum surface so the panel renders even before /api/needs lands.
  // Real shape lives in the dept needs.yaml; the panel only relies on
  // ids the resolver endpoint already validates.
];

export function ResolutionsAdminPanel(): JSX.Element {
  const [rows, setRows] = useState<RunnerSpecRow[]>([]);
  const [connectors, setConnectors] = useState<ConnectorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [historyFor, setHistoryFor] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  const refresh = async () => {
    setLoading(true);
    try {
      const [specs, conns] = await Promise.all([
        listRunnerSpecs(),
        listConnectors(),
      ]);
      setRows(specs);
      setConnectors(conns);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const websearchAvailable = useMemo(
    () => connectors.some((c) => c.category === "web_search"),
    [connectors],
  );

  const onShowHistory = async (specId: string) => {
    setHistoryFor(specId);
    try {
      const items = await getSpecHistory(specId);
      setHistory(items);
    } catch {
      setHistory([]);
    }
  };

  if (loading) {
    return <p className="text-sm text-text-secondary">Loading…</p>;
  }

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">
          Resolutions
        </h2>
        <p className="mt-1 text-sm text-text-secondary">
          Edit any per-need binding. Each save runs a smoke test before
          committing; failures preserve the previous spec.
        </p>
      </header>
      <ul className="space-y-3">
        {rows.map((row) => {
          const need: ResolveRowNeed = {
            department_id: row.department_id,
            need_id: row.need_id,
            description:
              KNOWN_NEEDS.find(
                (n) =>
                  n.department_id === row.department_id &&
                  n.need_id === row.need_id,
              )?.description ?? "",
            shape: KNOWN_NEEDS.find(
              (n) =>
                n.department_id === row.department_id &&
                n.need_id === row.need_id,
            )?.shape ?? "any",
          };
          return (
            <li key={row.id}>
              <ResolveRow
                need={need}
                spec={row}
                status={
                  row.resolution_mode === "catalog"
                    ? "resolved-catalog"
                    : "resolved-manual"
                }
                connectorId={row.connector_id}
                connectorCategory={
                  connectors.find((c) => c.id === row.connector_id)
                    ?.category ?? "financial"
                }
                endpointOptions={[]}
                websearchAvailable={websearchAvailable}
                onSaved={() => void refresh()}
              />
              <button
                type="button"
                className="text-xs text-accent-primary mt-1"
                onClick={() => void onShowHistory(row.id)}
              >
                History
              </button>
              {historyFor === row.id ? (
                <ul className="mt-2 text-xs text-text-secondary">
                  {history.length === 0 ? (
                    <li>No history.</li>
                  ) : (
                    history.map((h, i) => (
                      <li key={i}>
                        [{h.kind}] {h.status}
                        {h.error_message ? ` — ${h.error_message}` : ""}
                        {" — "}
                        {h.created_at}
                      </li>
                    ))
                  )}
                </ul>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
