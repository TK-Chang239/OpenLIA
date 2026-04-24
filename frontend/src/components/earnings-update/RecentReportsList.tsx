import { RecentReport } from "../../api/earnings-update";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RecentReport[];
  onOpenReport: (id: string) => void;
  onOpenCabinet: () => void;
}

export function RecentReportsList({
  reports,
  onOpenReport,
  onOpenCabinet,
}: Props) {
  return (
    <section>
      <header className="flex items-center justify-between px-6 pt-5 pb-3">
        <h3 className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em]">
          Recent Reports
        </h3>
        <button
          type="button"
          onClick={onOpenCabinet}
          className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]"
        >
          Open Cabinet →
        </button>
      </header>
      {reports.length === 0 ? (
        <div className="mx-6 mb-4 text-center py-8 text-sm text-[--color-text-tertiary]">
          On-Demand reports and automated reports will appear here
        </div>
      ) : (
        <div>
          {reports.map((r) => (
            <ReportRowItem key={r.id} report={r} onOpen={onOpenReport} />
          ))}
        </div>
      )}
    </section>
  );
}
