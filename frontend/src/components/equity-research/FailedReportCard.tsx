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
}

export function FailedReportCard({ report, navigate }: Props): JSX.Element {
  async function handleRetry(): Promise<void> {
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
      <button
        type="button"
        onClick={() => void fetch(`/reports/${report.id}`, { method: "DELETE" })}
      >
        Delete
      </button>
    </div>
  );
}
