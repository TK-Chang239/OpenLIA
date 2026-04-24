import type { RecentReport } from "../../api/morning-briefing";
import { MBReportCard } from "./MBReportCard";

interface MBArchiveViewProps {
  reports: RecentReport[];
  loading: boolean;
  onOpen: (report: RecentReport) => void;
}

function groupByDate(reports: RecentReport[]): Record<string, RecentReport[]> {
  const groups: Record<string, RecentReport[]> = {};
  for (const r of reports) {
    const key = new Date(r.created_at).toLocaleDateString();
    (groups[key] ??= []).push(r);
  }
  return groups;
}

export function MBArchiveView({
  reports,
  loading,
  onOpen,
}: MBArchiveViewProps) {
  if (loading) {
    return (
      <div className="text-sm text-muted-foreground">Loading briefings…</div>
    );
  }
  if (reports.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">
        No Morning Briefings yet. Use "Generate Briefing" to create one.
      </div>
    );
  }
  const groups = groupByDate(reports);
  return (
    <div className="space-y-4">
      {Object.entries(groups).map(([date, list]) => (
        <section key={date}>
          <h3 className="text-sm font-semibold text-muted-foreground mb-2">
            {date}
          </h3>
          <div className="space-y-2">
            {list.map((r) => (
              <MBReportCard key={r.id} report={r} onOpen={onOpen} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
