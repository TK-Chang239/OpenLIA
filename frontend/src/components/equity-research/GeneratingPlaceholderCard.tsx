import type { JSX } from "react";

export interface GeneratingReport {
  id: string;
  status: "generating";
  started_at?: string | null;
  original_request?: { user_input?: string | null } | null;
}

interface Props {
  report: GeneratingReport;
}

export function GeneratingPlaceholderCard({ report }: Props): JSX.Element {
  const elapsedSec = report.started_at
    ? Math.floor((Date.now() - new Date(report.started_at).getTime()) / 1000)
    : 0;
  const title = report.original_request?.user_input ?? "Generating report";

  async function handleCancel(): Promise<void> {
    if (!confirm("Cancel this report? Partial progress will be discarded.")) return;
    await fetch(`/reports/${report.id}`, { method: "DELETE" });
  }

  return (
    <div className="card card--generating">
      <div className="spinner" />
      <h3>{title}</h3>
      <p>
        {Math.floor(elapsedSec / 60)}:{(elapsedSec % 60).toString().padStart(2, "0")} elapsed
      </p>
      <button type="button" onClick={() => void handleCancel()}>
        Cancel
      </button>
    </div>
  );
}
