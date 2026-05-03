import { useEffect, useState } from "react";
import { ResolveRow, type ResolveRowNeed, type RowStatus } from "./ResolveRow";
import type { EndpointOption } from "./EndpointPicker";
import {
  listRunnerSpecs,
  type RunnerSpecRow,
} from "../../api/runner_specs";
import { listConnectors, type ConnectorRow } from "../../api/connectors";

interface Props {
  needs: ResolveRowNeed[];
  onAllResolved: () => void;
}

interface ConnectorEndpoints {
  connector: ConnectorRow;
  options: EndpointOption[];
}

function statusFor(spec: RunnerSpecRow | undefined): RowStatus {
  if (!spec) return "unresolved";
  const mode = (spec.resolution_mode ?? "catalog") as RunnerSpecRow["resolution_mode"];
  if (mode === "catalog") return "resolved-catalog";
  return "resolved-manual";
}

export function ResolveStep({ needs, onAllResolved }: Props) {
  const [specs, setSpecs] = useState<RunnerSpecRow[]>([]);
  const [connectors, setConnectors] = useState<ConnectorEndpoints[]>([]);
  const [selectedConnectorId, setSelectedConnectorId] = useState<string>("");

  useEffect(() => {
    void Promise.all([listRunnerSpecs(), listConnectors()]).then(
      ([specRows, connectorRows]) => {
        setSpecs(specRows);
        // Endpoint options aren't fetched per-connector here yet; the UI
        // surfaces what's already cached on the connector row. The
        // backend's existing /api/connectors/{id} returns cached_tools or
        // cached_python_callables; for the wizard we keep this minimal.
        setConnectors(
          connectorRows.map((c) => ({ connector: c, options: [] })),
        );
        if (connectorRows.length > 0 && !selectedConnectorId) {
          setSelectedConnectorId(connectorRows[0]!.id);
        }
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const specByKey = new Map(
    specs.map((s) => [`${s.department_id}/${s.need_id}`, s] as const),
  );
  const allResolved = needs.every((n) =>
    specByKey.has(`${n.department_id}/${n.need_id}`),
  );
  const websearchAvailable = connectors.some(
    (c) => c.connector.category === "web_search",
  );
  const selected = connectors.find((c) => c.connector.id === selectedConnectorId);

  return (
    <div className="resolve-step">
      <header>
        <h2>Resolve runner needs</h2>
        <p>
          Pick an endpoint (or a URL via Websearch) for each need below.
          Each save runs a smoke test before persisting.
        </p>
      </header>
      <div className="resolve-step-connector-picker">
        <label>
          Connector:
          <select
            value={selectedConnectorId}
            onChange={(e) => setSelectedConnectorId(e.target.value)}
          >
            {connectors.map((c) => (
              <option key={c.connector.id} value={c.connector.id}>
                {c.connector.display_name} ({c.connector.category})
              </option>
            ))}
          </select>
        </label>
      </div>
      <ul className="resolve-step-rows">
        {needs.map((need) => {
          const spec = specByKey.get(`${need.department_id}/${need.need_id}`);
          return (
            <li key={`${need.department_id}/${need.need_id}`}>
              <ResolveRow
                need={need}
                spec={spec}
                status={statusFor(spec)}
                connectorId={selectedConnectorId}
                connectorCategory={selected?.connector.category ?? "financial"}
                endpointOptions={selected?.options ?? []}
                websearchAvailable={websearchAvailable}
                onSaved={(saved) =>
                  setSpecs((prev) => {
                    const filtered = prev.filter(
                      (p) =>
                        p.department_id !== saved.department_id ||
                        p.need_id !== saved.need_id,
                    );
                    return [...filtered, saved];
                  })
                }
              />
            </li>
          );
        })}
      </ul>
      <footer>
        <button type="button" onClick={onAllResolved} disabled={!allResolved}>
          Continue (all resolved)
        </button>
      </footer>
    </div>
  );
}
