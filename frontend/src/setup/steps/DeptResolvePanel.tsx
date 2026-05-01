import { useEffect, useState } from "react";
import {
  listDeptProposedSpecs,
  resolveDeptProposedSpecs,
  type ProposedSpec,
} from "../../api/connectors";

interface Props {
  departmentId: string;
  label: string;
}

function calleeLabel(spec: Record<string, unknown>): string {
  const tool = spec["tool_name"];
  const method = spec["method"] ?? spec["qualname"];
  if (typeof tool === "string" && tool.length > 0) return tool;
  if (typeof method === "string" && method.length > 0) return method;
  return "(unresolved)";
}

export function DeptResolvePanel({ departmentId, label }: Props) {
  const [proposals, setProposals] = useState<ProposedSpec[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDeptProposedSpecs(departmentId)
      .then((rows) => {
        if (!cancelled) setProposals(rows);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load proposals.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [departmentId]);

  const onResolve = async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await resolveDeptProposedSpecs(departmentId);
      setProposals(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section
      data-testid={`dept-resolve-panel-${departmentId}`}
      className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-text-primary">{label}</h3>
        <button
          type="button"
          onClick={onResolve}
          disabled={loading}
          className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {loading ? "Resolving..." : `Resolve ${label}`}
        </button>
      </header>

      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      {proposals.length === 0 && !loading ? (
        <p className="text-xs text-text-secondary">
          No proposals yet. Click Resolve to generate them.
        </p>
      ) : null}

      <ul className="space-y-2">
        {proposals.map((p) => (
          <li
            key={`${p.department_id}:${p.need_id}`}
            data-testid={`dept-need-row-${p.department_id}-${p.need_id}`}
            className="rounded-md border border-border-subtle bg-bg-base p-2 text-xs"
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-mono text-text-primary">{p.need_id}</span>
              {p.unsatisfiable ? (
                <span className="text-feedback-error">
                  No connector provides this data
                </span>
              ) : (
                <span className="font-mono text-text-secondary">
                  {calleeLabel(p.proposed_spec)}
                  {p.connector_id ? ` @ ${p.connector_id.slice(0, 8)}` : ""}
                </span>
              )}
            </div>
            {p.error ? (
              <p className="mt-1 text-feedback-error">{p.error}</p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
