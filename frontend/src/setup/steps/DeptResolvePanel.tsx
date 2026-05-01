import { useEffect, useState } from "react";
import {
  approveDeptSpec,
  listConnectors,
  listDeptProposedSpecs,
  resolveDeptNeed,
  resolveDeptProposedSpecs,
  type ProposedSpec,
} from "../../api/connectors";
import { refreshDeptHealth } from "../../store/dept-health";

const SNAPSHOT_KEY_PREFIX = "openlia.dept-resolve-snapshot:";

function readSnapshot(departmentId: string): string[] | null {
  try {
    const raw = sessionStorage.getItem(`${SNAPSHOT_KEY_PREFIX}${departmentId}`);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.map(String).sort() : null;
  } catch {
    return null;
  }
}

function writeSnapshot(departmentId: string, ids: string[]): void {
  try {
    sessionStorage.setItem(
      `${SNAPSHOT_KEY_PREFIX}${departmentId}`,
      JSON.stringify([...ids].sort()),
    );
  } catch {
    /* ignore quota / disabled storage */
  }
}

function arraysEqual(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i += 1) {
    if (a[i] !== b[i]) return false;
  }
  return true;
}

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
  const [stale, setStale] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await listDeptProposedSpecs(departmentId);
        if (cancelled) return;
        setProposals(rows);
        if (rows.length === 0) {
          setStale(false);
          return;
        }
        const snapshot = readSnapshot(departmentId);
        if (snapshot === null) {
          setStale(false);
          return;
        }
        const conns = await listConnectors();
        if (cancelled) return;
        const currentIds = conns.map((c) => c.id).sort();
        setStale(!arraysEqual(currentIds, snapshot));
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load proposals.",
          );
        }
      }
    })();
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
      try {
        const conns = await listConnectors();
        writeSnapshot(
          departmentId,
          conns.map((c) => c.id),
        );
        setStale(false);
      } catch {
        /* snapshot is best-effort */
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Resolve failed.");
    } finally {
      setLoading(false);
    }
  };

  const onApprove = async (needId: string) => {
    setError(null);
    try {
      await approveDeptSpec(departmentId, needId);
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
    }
  };

  const onResolveNeed = async (needId: string) => {
    setError(null);
    try {
      const updated = await resolveDeptNeed(departmentId, needId);
      setProposals((prev) =>
        prev.map((p) => (p.need_id === needId ? updated : p)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-resolve failed.");
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

      {stale ? (
        <p
          role="status"
          className="rounded-md border border-feedback-warning bg-feedback-warning/10 px-2 py-1 text-xs text-feedback-warning"
        >
          Connectors changed since last resolve. Re-resolve to factor them in.
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
            <div className="mt-1 flex gap-2">
              {!p.unsatisfiable && p.connector_id ? (
                <button
                  type="button"
                  onClick={() => onApprove(p.need_id)}
                  className="rounded-md bg-accent-primary px-2 py-0.5 text-xs font-medium text-white hover:bg-accent-hover"
                >
                  Approve
                </button>
              ) : null}
              <button
                type="button"
                onClick={() => onResolveNeed(p.need_id)}
                className="rounded-md border border-border-subtle px-2 py-0.5 text-xs text-text-primary hover:bg-surface-hover"
              >
                Re-resolve
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
