/**
 * V3RunsPopover — chat-header dropdown adapter for v3 runs.
 *
 * Drop-in replacement for ``ChatHistoryPopover`` (used by the
 * TopBar's history dropdown) that reads from ``listV3Runs()``
 * instead of /api/chat/sessions. v3 has no session model — each run
 * is one-shot and treated as a "session" for nav purposes.
 *
 * Capabilities are intentionally narrower than the chat popover:
 * select + delete only. v3 runs don't support pin/archive/rename
 * server-side, so the row only exposes the delete affordance.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Trash } from "lucide-react";

import { type V3ReportSummary, deleteV3Run, listV3Runs } from "../../api/equity-research-v3";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

interface Props {
  activeSessionId: string | null;
  onSelect: (reportId: string) => void;
  onActiveDeleted: () => void;
  onClose: () => void;
}

const SEARCH_DEBOUNCE_MS = 250;

export function V3RunsPopover({
  activeSessionId,
  onSelect,
  onActiveDeleted,
  onClose,
}: Props): JSX.Element {
  const ref = useRef<HTMLDivElement>(null);
  const [rows, setRows] = useState<V3ReportSummary[] | null>(null);
  const [searchInput, setSearchInput] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [pendingDelete, setPendingDelete] = useState<V3ReportSummary | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const r = await listV3Runs();
      setRows(r);
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load runs");
      setRows([]);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const t = window.setTimeout(
      () => setDebouncedQuery(searchInput.trim().toLowerCase()),
      SEARCH_DEBOUNCE_MS,
    );
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    const onMouseDown = (e: MouseEvent) => {
      const node = ref.current;
      if (!node) return;
      if (e.target instanceof Node && node.contains(e.target)) return;
      onClose();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onMouseDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onMouseDown);
    };
  }, [onClose]);

  const visible = (rows ?? []).filter((r) =>
    debouncedQuery ? r.subject.toLowerCase().includes(debouncedQuery) : true,
  );

  return (
    <>
      <div
        ref={ref}
        role="menu"
        data-testid="v3-runs-popover"
        className="absolute left-0 top-full z-50 mt-1 flex max-h-[60vh] w-72 flex-col overflow-hidden rounded-md border border-border-subtle bg-bg-base shadow-lg"
      >
        <div className="px-3 pb-2 pt-3">
          <label className="relative flex items-center">
            <Search
              size={12}
              aria-hidden
              className="absolute left-2 text-[--color-text-tertiary]"
            />
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search v3 runs"
              aria-label="Search v3 runs"
              className="w-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] py-1 pl-7 pr-2 text-xs text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            />
          </label>
        </div>

        <div className="flex-1 overflow-y-auto px-2 pb-3">
          {loadError ? (
            <p className="mt-3 px-2 text-xs text-[--color-feedback-danger]">
              {loadError}
            </p>
          ) : null}
          {rows === null ? (
            <p className="mt-3 px-2 text-xs text-[--color-text-tertiary]">Loading…</p>
          ) : visible.length === 0 ? (
            <p className="mt-3 px-2 text-xs text-[--color-text-tertiary]">
              {debouncedQuery ? "No matching runs." : "No v3 runs yet."}
            </p>
          ) : (
            <ul className="mt-1 space-y-0.5">
              {visible.map((row) => {
                const active = row.report_id === activeSessionId;
                return (
                  <li
                    key={row.report_id}
                    data-testid={`v3-runs-popover-row-${row.report_id}`}
                    className={`group flex items-center gap-2 rounded-md px-2 py-1.5 text-sm ${
                      active
                        ? "bg-[--color-surface-active] text-[--color-text-primary]"
                        : "text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelect(row.report_id)}
                      className="flex min-w-0 flex-1 flex-col text-left"
                    >
                      <span className="truncate text-[13px]">{row.subject}</span>
                      <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                        {row.status} · {formatDate(row.created_at)}
                      </span>
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete run ${row.subject}`}
                      onClick={() => setPendingDelete(row)}
                      className="hidden rounded p-1 text-[--color-feedback-error] hover:bg-[--color-surface-hover] group-hover:inline-flex"
                    >
                      <Trash size={12} />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={pendingDelete !== null}
        title="Delete this v3 run?"
        description={
          pendingDelete
            ? `Permanently removes "${pendingDelete.subject}" and its sections, charts, and citations.`
            : undefined
        }
        confirmLabel="Delete"
        destructive
        onCancel={() => setPendingDelete(null)}
        onConfirm={async () => {
          const target = pendingDelete;
          setPendingDelete(null);
          if (!target) return;
          try {
            await deleteV3Run(target.report_id);
          } catch {
            /* surface refresh below; row stays or refreshes from list */
          }
          if (target.report_id === activeSessionId) {
            onActiveDeleted();
          }
          refresh();
        }}
      />
    </>
  );
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}
