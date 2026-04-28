import { useState } from "react";
import {
  approveSpec,
  reResolveSpecs,
  type ProposedSpec,
} from "../../api/connectors";
import { refreshDeptHealth } from "../../store/dept-health";

interface Props {
  connectorId: string;
  proposal: ProposedSpec;
  onChanged: () => void;
  onTryDifferent?: () => void;
}

function paramBindings(spec: Record<string, unknown>): Array<[string, unknown]> {
  const bindings = (spec["param_bindings"] ?? spec["params"] ?? {}) as Record<
    string,
    unknown
  >;
  if (!bindings || typeof bindings !== "object") return [];
  return Object.entries(bindings);
}

function calleeLabel(spec: Record<string, unknown>): string {
  const tool = spec["tool_name"];
  const method = spec["method"] ?? spec["qualname"];
  if (typeof tool === "string") return tool;
  if (typeof method === "string") return method;
  return "(unknown)";
}

export function PerNeedReviewCard({
  connectorId,
  proposal,
  onChanged,
  onTryDifferent,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onApprove = async () => {
    setBusy(true);
    setError(null);
    try {
      await approveSpec(connectorId, proposal.department_id, proposal.need_id);
      await refreshDeptHealth();
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    } finally {
      setBusy(false);
    }
  };

  const onResolve = async () => {
    setBusy(true);
    setError(null);
    try {
      await reResolveSpecs(connectorId);
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-resolve failed.");
    } finally {
      setBusy(false);
    }
  };

  const bindings = paramBindings(proposal.proposed_spec);

  return (
    <article
      data-testid={`per-need-card-${proposal.department_id}-${proposal.need_id}`}
      className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <header className="flex items-baseline justify-between gap-3">
        <div>
          <h4 className="text-sm font-medium text-text-primary">
            {proposal.department_id}
          </h4>
          <p className="text-xs text-text-secondary">need: {proposal.need_id}</p>
        </div>
        <span className="text-xs font-mono text-text-secondary">
          {calleeLabel(proposal.proposed_spec)}
        </span>
      </header>

      {bindings.length > 0 ? (
        <table className="w-full text-xs">
          <thead className="text-text-secondary">
            <tr>
              <th className="text-left">param</th>
              <th className="text-left">binding</th>
            </tr>
          </thead>
          <tbody>
            {bindings.map(([k, v]) => (
              <tr key={k} className="border-t border-border-subtle">
                <td className="font-mono">{k}</td>
                <td className="font-mono">{JSON.stringify(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}

      <div>
        <p className="text-xs text-text-secondary">canary value</p>
        <pre className="mt-1 overflow-auto rounded-md border border-border-subtle bg-bg-base p-2 font-mono text-xs text-text-primary">
          {JSON.stringify(proposal.canary_value, null, 2)}
        </pre>
      </div>

      {proposal.error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {proposal.error}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onApprove}
          disabled={busy}
          className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          Approve
        </button>
        <button
          type="button"
          onClick={onResolve}
          disabled={busy}
          className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover disabled:opacity-50"
        >
          Re-resolve
        </button>
        {onTryDifferent ? (
          <button
            type="button"
            onClick={onTryDifferent}
            disabled={busy}
            className="rounded-md border border-border-subtle px-3 py-1 text-xs text-text-primary hover:bg-surface-hover disabled:opacity-50"
          >
            Try a different connector
          </button>
        ) : null}
      </div>
    </article>
  );
}
