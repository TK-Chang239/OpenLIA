import { useState } from "react";

import type { RecentReport } from "../../api/morning-briefing";
import { reportPdfUrl } from "../../api/reports";

interface MBReportCardProps {
  report: RecentReport;
  onOpen: (report: RecentReport) => void;
  now?: Date;
}

function isWithinHour(createdAt: string, now: Date): boolean {
  const t = new Date(createdAt).getTime();
  return now.getTime() - t < 60 * 60 * 1000;
}

export function MBReportCard({ report, onOpen, now }: MBReportCardProps) {
  const [opened, setOpened] = useState(false);
  const reference = now ?? new Date();
  const fresh = isWithinHour(report.created_at, reference);
  const showNew = fresh && !opened;

  const when = new Date(report.created_at).toLocaleString();

  const handleOpen = () => {
    setOpened(true);
    onOpen(report);
  };

  return (
    <div
      className="rounded-[var(--radius-lg,0.5rem)] border p-3 shadow-sm flex items-center justify-between gap-3"
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-base)",
      }}
      data-testid="mb-report-card"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <div className="font-medium truncate">{report.title}</div>
          {showNew && (
            <span
              data-testid="mb-report-new-badge"
              className="text-[10px] uppercase font-semibold rounded px-1 py-0.5"
              style={{
                background: "var(--color-accent-primary)",
                color: "var(--color-accent-on)",
              }}
            >
              New
            </span>
          )}
        </div>
        <div
          className="text-xs"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {when}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="text-sm underline"
          onClick={handleOpen}
          data-testid="mb-report-open"
        >
          Open
        </button>
        <a
          href={reportPdfUrl(report.id)}
          download
          className="text-sm underline"
          data-testid="mb-report-download"
        >
          {"↓ Download"}
        </a>
      </div>
    </div>
  );
}
