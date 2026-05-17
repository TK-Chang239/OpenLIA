import { useState } from "react";

interface Props {
  newReportId: string;
}

export function RevisionInProgressChip({ newReportId }: Props) {
  const [cancelled, setCancelled] = useState(false);

  async function handleCancel() {
    if (!confirm("Cancel this revision? Partial progress will be discarded.")) return;
    await fetch(`/reports/${newReportId}`, { method: "DELETE" });
    setCancelled(true);
  }

  return (
    <div className={`chip chip--revision ${cancelled ? "chip--cancelled" : ""}`}>
      <span className="spinner" aria-hidden="true" />
      <span>{cancelled ? "Revision cancelled" : "Revising the report based on our discussion..."}</span>
      {!cancelled && (
        <button onClick={handleCancel}>Cancel revision</button>
      )}
    </div>
  );
}
