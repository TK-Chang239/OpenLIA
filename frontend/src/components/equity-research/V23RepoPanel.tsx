/**
 * V23RepoPanel — list of the user's v2.3 runs with download + delete.
 *
 * Lives inside the v2.3 preview surface (above the composer) so the
 * v2.3 engine has its own Repository view without touching the v1/v2.2
 * Repository page. When the v2.3 engine graduates from preview, this
 * panel can fold into the main Repository surface.
 */
import { Download, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { type JSX, useCallback, useEffect, useState } from "react";

import {
  type V23RunStatus,
  type V23RunSummary,
  deleteV23Run,
  listV23Runs,
  v23DocxUrl,
} from "../../api/equity-research-v2-3";

const STATUS_LABEL: Record<V23RunStatus, string> = {
  running: "Running",
  waiting_on_user: "Waiting",
  complete: "Complete",
  failed: "Failed",
};

const STATUS_COLOR: Record<V23RunStatus, string> = {
  running: "text-[--color-text-secondary]",
  waiting_on_user: "text-[--color-feedback-warning]",
  complete: "text-[--color-feedback-success]",
  failed: "text-[--color-feedback-danger]",
};

export interface V23RepoPanelProps {
  /** Optional callback when the user clicks a row — caller can resume
   *  / reattach by run_id. */
  onSelect?: (summary: V23RunSummary) => void;
  /** Bump this to trigger a fresh list — parent uses it to re-fetch
   *  once a streaming run produces a new persisted row. */
  refreshKey?: number;
}

export function V23RepoPanel({
  onSelect,
  refreshKey,
}: V23RepoPanelProps): JSX.Element {
  const [rows, setRows] = useState<V23RunSummary[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await listV23Runs({ limit: 50 });
      setRows(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "failed to load runs");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh, refreshKey]);

  const remove = async (run_id: string) => {
    if (!window.confirm("Delete this v2.3 run? This cannot be undone.")) return;
    setBusy(true);
    try {
      await deleteV23Run(run_id);
      setRows((prev) => (prev ?? []).filter((r) => r.run_id !== run_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      data-testid="er-v2-3-repo-panel"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated]"
    >
      <header className="flex items-center justify-between border-b border-[--color-border-subtle] px-3 py-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          Past v2.3 runs {rows ? `· ${rows.length}` : ""}
        </span>
        <button
          type="button"
          onClick={refresh}
          aria-label="Refresh v2.3 runs"
          disabled={busy}
          className="inline-flex h-6 w-6 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:opacity-40"
        >
          {busy ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
        </button>
      </header>

      {error ? (
        <div className="px-3 py-2 text-[12px] text-[--color-feedback-danger]">{error}</div>
      ) : null}

      {rows === null ? (
        <div className="px-3 py-3 text-[12px] text-[--color-text-tertiary]">Loading…</div>
      ) : rows.length === 0 ? (
        <div className="px-3 py-3 text-[12px] text-[--color-text-tertiary]">
          No v2.3 runs yet. Start one below.
        </div>
      ) : (
        <ul className="divide-y divide-[--color-border-subtle]">
          {rows.map((r) => (
            <li
              key={r.run_id}
              className="flex items-center gap-2 px-3 py-2"
              data-testid={`er-v2-3-repo-row-${r.run_id}`}
            >
              <button
                type="button"
                onClick={() => onSelect?.(r)}
                className="flex flex-1 flex-col items-start gap-[2px] text-left"
              >
                <span className="font-mono text-[11.5px] text-[--color-text-primary]">
                  {r.tickers.join(", ") || "(no tickers)"} · {r.report_type}
                </span>
                <span className="truncate text-[11px] text-[--color-text-tertiary]">
                  {r.raw_prompt.slice(0, 80)}
                  {r.raw_prompt.length > 80 ? "…" : ""}
                </span>
              </button>
              <span
                className={`font-mono text-[10px] uppercase tracking-[0.08em] ${STATUS_COLOR[r.status] ?? ""}`}
              >
                {STATUS_LABEL[r.status] ?? r.status}
              </span>
              {r.status === "complete" ? (
                <a
                  href={v23DocxUrl(r.run_id)}
                  download
                  aria-label="Download .docx"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
                >
                  <Download size={12} />
                </a>
              ) : null}
              <button
                type="button"
                onClick={() => remove(r.run_id)}
                aria-label="Delete run"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-feedback-danger]"
              >
                <Trash2 size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
