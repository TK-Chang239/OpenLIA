import type { RecentReport } from "../../api/morning-briefing";

interface MBReportCardProps {
  report: RecentReport;
  onOpen: (report: RecentReport) => void;
}

export function MBReportCard({ report, onOpen }: MBReportCardProps) {
  const when = new Date(report.created_at).toLocaleString();
  return (
    <div
      className="rounded-md border border-border bg-surface p-3 shadow-sm flex items-center justify-between gap-3"
      data-testid="mb-report-card"
    >
      <div className="min-w-0">
        <div className="font-medium truncate">{report.title}</div>
        <div className="text-xs text-muted-foreground">{when}</div>
      </div>
      <div className="flex items-center gap-2">
        <button
          type="button"
          className="text-sm text-primary hover:underline"
          onClick={() => onOpen(report)}
        >
          Open
        </button>
      </div>
    </div>
  );
}
