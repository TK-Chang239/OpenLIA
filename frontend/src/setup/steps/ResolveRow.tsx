import { useState } from "react";
import { EndpointPicker, type EndpointOption } from "./EndpointPicker";
import { SmokeFailurePanel } from "./SmokeFailurePanel";
import {
  resolveAndSaveSpec,
  type RunnerSpecRow,
  type SmokeFailure,
} from "../../api/runner_specs";

export type RowStatus = "resolved-catalog" | "resolved-manual" | "unresolved" | "draft";

export interface ResolveRowNeed {
  department_id: string;
  need_id: string;
  description: string;
  shape: string;
}

interface Props {
  need: ResolveRowNeed;
  spec?: RunnerSpecRow;
  status: RowStatus;
  connectorId: string;
  connectorCategory: string;
  endpointOptions: EndpointOption[];
  websearchAvailable: boolean;
  onSaved: (spec: RunnerSpecRow) => void;
  onOpenConnectorSettings?: () => void;
}

export function ResolveRow({
  need,
  spec,
  status,
  connectorId,
  connectorCategory,
  endpointOptions,
  websearchAvailable,
  onSaved,
  onOpenConnectorSettings,
}: Props) {
  const [editing, setEditing] = useState(status === "unresolved");
  const [mode, setMode] = useState<"manual_endpoint" | "websearch">(
    "manual_endpoint",
  );
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [hint, setHint] = useState("");
  const [websearchUrl, setWebsearchUrl] = useState("");
  const [saving, setSaving] = useState(false);
  const [warning, setWarning] = useState<string | null>(null);
  const [pendingWarning, setPendingWarning] = useState<string | null>(null);
  const [failure, setFailure] = useState<SmokeFailure | null>(null);

  const handleSave = async (manuallyOverridden: boolean) => {
    if (!endpoint) return;
    if (mode === "websearch" && !websearchUrl) return;
    setSaving(true);
    setFailure(null);
    setPendingWarning(null);
    try {
      const result = await resolveAndSaveSpec({
        department_id: need.department_id,
        need_id: need.need_id,
        connector_id: connectorId,
        resolution_mode: mode,
        user_picked_endpoint: endpoint,
        user_hint: hint || null,
        websearch_url: mode === "websearch" ? websearchUrl : null,
        manually_overridden: manuallyOverridden,
      });
      if (result.ok) {
        if (result.warning && !manuallyOverridden) {
          setPendingWarning(result.warning);
          return;
        }
        setWarning(result.warning);
        setEditing(false);
        onSaved(result.spec);
      } else {
        setFailure(result.failure);
      }
    } finally {
      setSaving(false);
    }
  };

  const websearchDisabled = !websearchAvailable;

  return (
    <div className="resolve-row" data-status={status} data-need-id={need.need_id}>
      <div className="resolve-row-header">
        <strong>{need.need_id}</strong>
        <span className="resolve-row-shape">{need.shape}</span>
        <span className="resolve-row-status-badge" data-status={status}>
          {status}
        </span>
      </div>
      <p>{need.description}</p>
      {!editing && spec ? (
        <div className="resolve-row-summary">
          <span>{String(spec.spec["tool_name"] ?? spec.spec["method"] ?? "")}</span>
          <button type="button" onClick={() => setEditing(true)}>
            Edit
          </button>
        </div>
      ) : null}
      {editing ? (
        <div className="resolve-row-form">
          <div role="radiogroup" aria-label="Resolution mode">
            <label>
              <input
                type="radio"
                name={`mode-${need.need_id}`}
                value="manual_endpoint"
                checked={mode === "manual_endpoint"}
                onChange={() => setMode("manual_endpoint")}
              />
              Connector + endpoint
            </label>
            <label>
              <input
                type="radio"
                name={`mode-${need.need_id}`}
                value="websearch"
                checked={mode === "websearch"}
                onChange={() => setMode("websearch")}
                disabled={websearchDisabled}
                aria-disabled={websearchDisabled}
              />
              Websearch (URL)
              {websearchDisabled ? (
                <small> — install a web_search connector first</small>
              ) : null}
            </label>
          </div>
          {mode === "manual_endpoint" ? (
            <EndpointPicker
              options={endpointOptions}
              value={endpoint}
              onChange={setEndpoint}
              disabled={saving}
            />
          ) : (
            <input
              type="url"
              placeholder="https://example.com/page"
              value={websearchUrl}
              onChange={(e) => setWebsearchUrl(e.target.value)}
              disabled={saving}
              aria-label="Websearch URL"
            />
          )}
          <textarea
            placeholder="Optional hint for the resolver…"
            value={hint}
            onChange={(e) => setHint(e.target.value)}
            disabled={saving}
            aria-label="Resolver hint"
          />
          <div className="resolve-row-actions">
            <button
              type="button"
              onClick={() => handleSave(false)}
              disabled={saving || !endpoint}
            >
              Save and smoke
            </button>
          </div>
        </div>
      ) : null}
      {pendingWarning ? (
        <div className="resolve-row-warning-modal" role="dialog" aria-label="Resolver warning">
          <p>{pendingWarning}</p>
          <button type="button" onClick={() => handleSave(true)}>
            Proceed anyway
          </button>
          <button
            type="button"
            onClick={() => {
              setPendingWarning(null);
              setEditing(true);
            }}
          >
            Cancel
          </button>
        </div>
      ) : null}
      {warning && !editing ? (
        <p className="resolve-row-saved-warning">Saved with warning: {warning}</p>
      ) : null}
      {failure ? (
        <SmokeFailurePanel
          failure={failure}
          onRetry={() => handleSave(false)}
          onOpenConnectorSettings={
            failure.status === "auth" ? onOpenConnectorSettings : undefined
          }
        />
      ) : null}
    </div>
  );
}
