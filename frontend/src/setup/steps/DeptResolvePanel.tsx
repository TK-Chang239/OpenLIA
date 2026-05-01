import { useEffect, useState } from "react";
import {
  approveDeptSpec,
  listConnectors,
  listDeptProposedSpecs,
  listDeptResolveEvents,
  resolveDeptNeed,
  resolveDeptProposedSpecs,
  type ProposedSpec,
  type ResolveEvent,
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

function constantsSummary(spec: Record<string, unknown>): string {
  const constants = spec["constants"];
  if (!constants || typeof constants !== "object") return "";
  const entries = Object.entries(constants as Record<string, unknown>);
  if (entries.length === 0) return "";
  return entries
    .map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`)
    .join(", ");
}

function approvalKey(needId: string, connectorId: string | null): string {
  return `${needId}::${connectorId ?? ""}`;
}

function groupByNeed(
  proposals: ProposedSpec[],
): { needId: string; candidates: ProposedSpec[] }[] {
  const order: string[] = [];
  const buckets = new Map<string, ProposedSpec[]>();
  for (const p of proposals) {
    if (!buckets.has(p.need_id)) {
      buckets.set(p.need_id, []);
      order.push(p.need_id);
    }
    buckets.get(p.need_id)!.push(p);
  }
  return order.map((needId) => ({
    needId,
    candidates: buckets.get(needId)!,
  }));
}

export function DeptResolvePanel({ departmentId, label }: Props) {
  const [proposals, setProposals] = useState<ProposedSpec[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [stale, setStale] = useState<boolean>(false);
  const [events, setEvents] = useState<ResolveEvent[]>([]);
  const [approving, setApproving] = useState<Set<string>>(() => new Set());
  const [approved, setApproved] = useState<Set<string>>(() => new Set());

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
    setEvents([]);
    setApproved(new Set());
    let pollHandle: ReturnType<typeof setInterval> | null = null;
    pollHandle = setInterval(() => {
      listDeptResolveEvents(departmentId)
        .then((rows) => setEvents(rows))
        .catch(() => {
          /* polling is best-effort */
        });
    }, 600);
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
      if (pollHandle !== null) clearInterval(pollHandle);
      try {
        const final = await listDeptResolveEvents(departmentId);
        setEvents(final);
      } catch {
        /* ignore */
      }
      setLoading(false);
    }
  };

  const approveOne = async (
    needId: string,
    connectorId: string,
  ): Promise<boolean> => {
    const key = approvalKey(needId, connectorId);
    if (approving.has(key) || approved.has(needId)) return false;
    setApproving((prev) => {
      const next = new Set(prev);
      next.add(key);
      return next;
    });
    try {
      await approveDeptSpec(departmentId, needId, connectorId);
      setApproved((prev) => {
        const next = new Set(prev);
        next.add(needId);
        return next;
      });
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Approval failed.");
      return false;
    } finally {
      setApproving((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const onApprove = async (needId: string, connectorId: string) => {
    setError(null);
    const ok = await approveOne(needId, connectorId);
    if (ok) await refreshDeptHealth();
  };

  const onApproveAll = async () => {
    setError(null);
    const groups = groupByNeed(proposals);
    let any = false;
    for (const { needId, candidates } of groups) {
      if (approved.has(needId)) continue;
      const pick = candidates.find(
        (c) => !c.unsatisfiable && c.connector_id !== null,
      );
      if (!pick || !pick.connector_id) continue;
      const ok = await approveOne(needId, pick.connector_id);
      if (ok) any = true;
    }
    if (any) await refreshDeptHealth();
  };

  const onResolveNeed = async (
    needId: string,
    options?: { excludeConnectorIds?: string[] },
  ) => {
    setError(null);
    try {
      const updated = await resolveDeptNeed(departmentId, needId, options);
      setProposals((prev) => [
        ...prev.filter((p) => p.need_id !== needId),
        ...updated,
      ]);
      setApproved((prev) => {
        if (!prev.has(needId)) return prev;
        const next = new Set(prev);
        next.delete(needId);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Re-resolve failed.");
    }
  };

  const groups = groupByNeed(proposals);
  const approvableCount = groups.reduce((acc, g) => {
    if (approved.has(g.needId)) return acc;
    const pick = g.candidates.find(
      (c) => !c.unsatisfiable && c.connector_id !== null,
    );
    return pick ? acc + 1 : acc;
  }, 0);

  return (
    <section
      data-testid={`dept-resolve-panel-${departmentId}`}
      className="space-y-2 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <header className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-text-primary">{label}</h3>
        <div className="flex items-center gap-2">
          {approvableCount > 0 ? (
            <button
              type="button"
              onClick={onApproveAll}
              className="rounded-md border border-border-subtle px-3 py-1 text-xs font-medium text-text-primary hover:bg-surface-hover"
            >
              Approve all ({approvableCount})
            </button>
          ) : null}
          <button
            type="button"
            onClick={onResolve}
            disabled={loading}
            className="rounded-md bg-accent-primary px-3 py-1 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {loading
              ? "Resolving..."
              : proposals.length > 0
                ? `Re-resolve ${label}`
                : `Resolve ${label}`}
          </button>
        </div>
      </header>

      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      {events.length > 0 ? (
        <details
          className="rounded-md border border-border-subtle bg-bg-base p-2 text-xs"
          open={loading}
        >
          <summary className="cursor-pointer text-text-secondary">
            Tool calls ({events.length})
          </summary>
          <ul className="mt-1 space-y-0.5 font-mono text-text-secondary">
            {events.slice(-20).map((e, idx) => (
              <li key={idx}>
                {e.name}({(JSON.stringify(e.arguments ?? {}) ?? "{}").slice(0, 100)})
                {e.need_id ? (
                  <span className="ml-1 text-text-tertiary">→ {e.need_id}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {stale ? (
        <p
          role="status"
          className="rounded-md border border-feedback-warning bg-feedback-warning/10 px-2 py-1 text-xs text-feedback-warning"
        >
          Connectors changed since last resolve. Re-resolve to factor them in.
        </p>
      ) : null}

      {groups.length === 0 && !loading ? (
        <p className="text-xs text-text-secondary">
          No proposals yet. Click Resolve to generate them.
        </p>
      ) : null}

      <ul className="space-y-2">
        {groups.map(({ needId, candidates }) => {
          const isApproved = approved.has(needId);
          const usableCandidates = candidates.filter(
            (c) => !c.unsatisfiable && c.connector_id !== null,
          );
          const allUnsat = usableCandidates.length === 0;
          return (
            <li
              key={`${departmentId}:${needId}`}
              data-testid={`dept-need-row-${departmentId}-${needId}`}
              className="rounded-md border border-border-subtle bg-bg-base p-2 text-xs"
            >
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-text-primary">{needId}</span>
                {allUnsat ? (
                  <span className="text-feedback-error">
                    No connector provides this data
                  </span>
                ) : isApproved ? (
                  <span className="text-xs font-medium text-feedback-success">
                    Approved
                  </span>
                ) : usableCandidates.length > 1 ? (
                  <span className="text-text-tertiary">
                    {usableCandidates.length} candidates
                  </span>
                ) : null}
              </div>
              <ul className="mt-1 space-y-1">
                {candidates.map((c, idx) => {
                  const key = approvalKey(needId, c.connector_id ?? null);
                  const callee = calleeLabel(c.proposed_spec);
                  const consts = constantsSummary(c.proposed_spec);
                  const cidShort = c.connector_id
                    ? c.connector_id.slice(0, 8)
                    : "";
                  return (
                    <li
                      key={`${needId}:${c.connector_id ?? "unsat"}:${idx}`}
                      className="rounded-md border border-border-subtle/60 bg-bg-elevated/40 p-1.5"
                    >
                      <div className="flex items-baseline justify-between gap-2">
                        <span className="font-mono text-text-secondary">
                          {c.unsatisfiable
                            ? "(no candidate)"
                            : `${callee}${cidShort ? ` @ ${cidShort}` : ""}`}
                        </span>
                      </div>
                      {consts ? (
                        <p className="mt-0.5 font-mono text-text-tertiary">
                          {consts}
                        </p>
                      ) : null}
                      {c.error ? (
                        <p className="mt-0.5 text-feedback-error">{c.error}</p>
                      ) : null}
                      {c.reason ? (
                        <p className="mt-0.5 italic text-text-tertiary">
                          {c.reason}
                        </p>
                      ) : null}
                      {!c.unsatisfiable && c.connector_id && !isApproved ? (
                        <div className="mt-1 flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() =>
                              onApprove(needId, c.connector_id as string)
                            }
                            disabled={approving.has(key)}
                            className="rounded-md bg-accent-primary px-2 py-0.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50"
                          >
                            {approving.has(key) ? "Approving..." : "Approve"}
                          </button>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
              <div className="mt-1 flex gap-2">
                <button
                  type="button"
                  onClick={() => onResolveNeed(needId)}
                  className="rounded-md border border-border-subtle px-2 py-0.5 text-xs text-text-primary hover:bg-surface-hover"
                >
                  Re-resolve
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
