import type { JSX } from "react";

export interface FailedReport {
  id: string;
  status: "failed" | "cancelled";
  failure_reason?: string | null;
  original_request?: { user_input?: string | null } | null;
}

interface Props {
  report: FailedReport;
  navigate: (path: string) => void;
  /** Optional override for the Retry button. Used by the v2.2 engine to
   *  re-fire its own SSE stream (v1 reports POST /reports/{id}/retry,
   *  which doesn't exist for pipeline_runs). When omitted, the v1
   *  retry endpoint is called. */
  onRetry?: () => void;
  /** Optional override for the Delete button. v2 reports skip deletion
   *  in this pass; pass `null` to hide the button entirely. */
  onDelete?: (() => void) | null;
}

export function FailedReportCard({
  report,
  navigate,
  onRetry,
  onDelete,
}: Props): JSX.Element {
  async function handleRetry(): Promise<void> {
    if (onRetry) {
      onRetry();
      return;
    }
    const resp = await fetch(`/reports/${report.id}/retry`, { method: "POST" });
    const { report_id } = (await resp.json()) as { report_id: string };
    navigate(`/equity-research?report_id=${report_id}`);
  }

  return (
    <div className={`card card--${report.status}`}>
      <h3>{report.original_request?.user_input ?? "Report"}</h3>
      {report.failure_reason ? <p>{report.failure_reason}</p> : null}
      <button type="button" onClick={() => void handleRetry()}>
        Retry
      </button>
      {onDelete === null ? null : (
        <button
          type="button"
          onClick={() =>
            onDelete
              ? onDelete()
              : void fetch(`/reports/${report.id}`, { method: "DELETE" })
          }
        >
          Delete
        </button>
      )}
    </div>
  );
}
