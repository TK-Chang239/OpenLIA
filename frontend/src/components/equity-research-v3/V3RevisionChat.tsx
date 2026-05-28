/**
 * V3RevisionChat — chat-style surface for revising a v3 report.
 *
 * Pattern: composer at the bottom, chronological revision history
 * above (each row is one user request + status badge). On submit:
 * POST ``/runs/{report_id}/revise`` to start a background revision,
 * then poll ``/runs/{report_id}/revisions`` every 2s while a row
 * shows ``status='running'`` so the list stays current without an
 * SSE subscription (which would add complexity for marginal value
 * at the 30s–5min revision durations we expect).
 *
 * The parent owns the report detail; when this component sees a
 * revision flip terminal it calls ``onRevisionComplete`` so the
 * parent re-fetches the report (latest section versions).
 */
import { AlertTriangle, Check, Loader2, Send } from "lucide-react";
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../api/_request";
import {
  type V3Revision,
  cancelV3Revision,
  listV3Revisions,
  startV3Revision,
} from "../../api/equity-research-v3";

interface Props {
  reportId: string;
  /** True when the parent report is in ``status='running'`` (e.g. an
   *  initial-generation run is still going). Disables the composer
   *  + hides the new-revision affordance — revisions only make sense
   *  on completed reports. */
  parentRunning?: boolean;
  /** Fired when the latest revision lands in a terminal state. The
   *  parent re-fetches the report so the latest section versions
   *  render. */
  onRevisionComplete: () => void;
}

const POLL_INTERVAL_MS = 2000;

function isTerminal(status: V3Revision["status"]): boolean {
  return status === "completed" || status === "failed" || status === "cancelled";
}

export function V3RevisionChat({
  reportId,
  parentRunning = false,
  onRevisionComplete,
}: Props): JSX.Element {
  const [revisions, setRevisions] = useState<V3Revision[] | null>(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Tracks which revision id has been "seen as in-flight" so we can
  // detect the live → terminal transition and fire onRevisionComplete
  // exactly once. Without this, polling would re-fire the callback
  // every tick after completion.
  const lastInFlightIdRef = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await listV3Revisions(reportId);
      setRevisions(rows);
      const latest = rows[rows.length - 1];
      if (latest && !isTerminal(latest.status)) {
        lastInFlightIdRef.current = latest.id;
      } else if (
        latest
        && isTerminal(latest.status)
        && lastInFlightIdRef.current === latest.id
      ) {
        lastInFlightIdRef.current = null;
        onRevisionComplete();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 503) {
        setRevisions([]);
        return;
      }
      // Transient network errors don't block the UI; let the next
      // tick recover.
    }
  }, [reportId, onRevisionComplete]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll while a revision is in flight. Stops as soon as the latest
  // row is terminal — the next user submit kicks off a fresh poll.
  useEffect(() => {
    if (!revisions) return;
    const latest = revisions[revisions.length - 1];
    if (!latest || isTerminal(latest.status)) return;
    const t = window.setInterval(() => {
      refresh();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(t);
  }, [revisions, refresh]);

  const inFlight = revisions?.some((r) => !isTerminal(r.status)) ?? false;
  const canSubmit =
    prompt.trim().length > 0 && !submitting && !inFlight && !parentRunning;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      await startV3Revision(reportId, { request: prompt.trim() });
      setPrompt("");
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setError(
          "Another revision is already in flight. Wait for it to finish or cancel it.",
        );
      } else {
        setError(err instanceof Error ? err.message : String(err));
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleCancel = async (revisionId: string) => {
    try {
      await cancelV3Revision(revisionId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  return (
    <section
      data-testid="er-v3-revision-chat"
      className="max-w-[640px] rounded-[12px] border border-[--color-border-subtle] bg-[--color-bg-elevated]"
    >
      <header className="border-b border-[--color-border-subtle] px-[18px] py-3">
        <h3 className="m-0 text-[13px] font-semibold text-[--color-text-primary]">
          Revise this report
        </h3>
        <p className="mt-[2px] text-[11.5px] text-[--color-text-tertiary]">
          Describe a change ("rewrite the bull case…", "add a competitor
          analysis section") and the engine will update the report in
          place. Each revision is one round; only one runs at a time.
        </p>
      </header>

      <div className="flex flex-col gap-2 px-[18px] py-3" data-testid="er-v3-revision-list">
        {revisions === null ? (
          <p className="text-[12px] text-[--color-text-tertiary]">
            Loading revisions…
          </p>
        ) : revisions.length === 0 ? (
          <p className="text-[12px] text-[--color-text-tertiary]">
            No revisions yet.
          </p>
        ) : (
          revisions.map((rev) => (
            <RevisionRow
              key={rev.id}
              revision={rev}
              onCancel={() => handleCancel(rev.id)}
            />
          ))
        )}
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="er-v3-revision-error"
          className="mx-[18px] mb-3 flex items-start gap-[6px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
        >
          <AlertTriangle size={13} strokeWidth={2} className="mt-[2px]" />
          <span>{error}</span>
        </div>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className="flex items-end gap-2 border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[18px] py-3"
      >
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            parentRunning
              ? "Wait for the initial run to finish…"
              : inFlight
                ? "A revision is in flight…"
                : "Describe the change you want."
          }
          disabled={!canSubmit && (parentRunning || inFlight)}
          rows={2}
          data-testid="er-v3-revision-input"
          className="min-h-[42px] flex-1 resize-none rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 py-2 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary] disabled:opacity-60"
        />
        <button
          type="submit"
          disabled={!canSubmit}
          data-testid="er-v3-revision-send"
          className="inline-flex h-[34px] items-center gap-[6px] rounded-md bg-[--color-accent-primary] px-3 text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
        >
          {submitting ? (
            <Loader2 size={13} strokeWidth={2} className="animate-spin" />
          ) : (
            <Send size={13} strokeWidth={2} />
          )}
          Send
        </button>
      </form>
    </section>
  );
}

function RevisionRow({
  revision,
  onCancel,
}: {
  revision: V3Revision;
  onCancel: () => void | Promise<void>;
}): JSX.Element {
  const isRunning = revision.status === "running";
  return (
    <div
      data-testid={`er-v3-revision-row-${revision.id}`}
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2"
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            #{revision.revision_index}
          </span>
          <RevisionStatusBadge status={revision.status} />
        </div>
        {isRunning ? (
          <button
            type="button"
            onClick={() => void onCancel()}
            data-testid={`er-v3-revision-cancel-${revision.id}`}
            className="rounded border border-[--color-border-subtle] px-2 py-[2px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-feedback-danger] hover:text-[--color-feedback-danger]"
          >
            Cancel
          </button>
        ) : null}
      </div>
      <p className="mt-1 text-[12.5px] leading-[1.5] text-[--color-text-primary]">
        {revision.request}
      </p>
      {revision.error_message ? (
        <p className="mt-1 text-[11.5px] text-[--color-feedback-danger]">
          {revision.error_message}
        </p>
      ) : null}
    </div>
  );
}

function RevisionStatusBadge({
  status,
}: {
  status: V3Revision["status"];
}): JSX.Element {
  const map = {
    running: {
      label: "Running",
      cls: "border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-secondary]",
      icon: <Loader2 size={10} strokeWidth={2} className="animate-spin" />,
    },
    completed: {
      label: "Completed",
      cls: "border-[rgba(168,204,0,0.4)] bg-[rgba(212,255,0,0.12)] text-[--color-feedback-success]",
      icon: <Check size={10} strokeWidth={2.4} />,
    },
    failed: {
      label: "Failed",
      cls: "border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] text-[--color-feedback-danger]",
      icon: <AlertTriangle size={10} strokeWidth={2} />,
    },
    cancelled: {
      label: "Cancelled",
      cls: "border-[--color-feedback-warning] bg-[rgba(255,180,0,0.08)] text-[--color-feedback-warning]",
      icon: null,
    },
  }[status];
  return (
    <span
      data-testid="er-v3-revision-status"
      className={`inline-flex items-center gap-[5px] rounded-full border px-2 py-[2px] font-mono text-[9.5px] uppercase tracking-[0.08em] ${map.cls}`}
    >
      {map.icon}
      {map.label}
    </span>
  );
}
