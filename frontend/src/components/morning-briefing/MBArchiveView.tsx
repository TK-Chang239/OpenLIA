import type { RecentReport } from "../../api/morning-briefing";
import { MBReportCard } from "./MBReportCard";

interface MBArchiveViewProps {
  reports: RecentReport[];
  loading: boolean;
  onOpen: (report: RecentReport) => void;
  onGoToSettings?: () => void;
}

interface DayGroup {
  key: string;
  heading: string;
  reports: RecentReport[];
}

function startOfDay(d: Date): Date {
  const x = new Date(d);
  x.setHours(0, 0, 0, 0);
  return x;
}

function dayHeading(date: Date, today: Date): string {
  const tStart = startOfDay(today);
  const dStart = startOfDay(date);
  const diffDays = Math.round(
    (tStart.getTime() - dStart.getTime()) / (24 * 3600 * 1000),
  );
  const weekday = date.toLocaleDateString(undefined, { weekday: "long" });
  const monthDayYear = date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  if (diffDays === 0) return `Today — ${weekday}, ${monthDayYear}`;
  if (diffDays === 1) return `Yesterday — ${weekday}, ${monthDayYear}`;
  return date.toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
  });
}

function groupReports(reports: RecentReport[], today: Date): DayGroup[] {
  const map = new Map<string, RecentReport[]>();
  for (const r of reports) {
    const date = new Date(r.created_at);
    const key = startOfDay(date).toISOString();
    const list = map.get(key) ?? [];
    list.push(r);
    map.set(key, list);
  }
  const out: DayGroup[] = [];
  for (const [key, list] of map) {
    const date = new Date(key);
    out.push({ key, heading: dayHeading(date, today), reports: list });
  }
  out.sort((a, b) => (a.key < b.key ? 1 : -1));
  return out;
}

function SunIcon({ size = 40 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      data-testid="mb-empty-sun"
      style={{ color: "var(--color-text-tertiary)" }}
    >
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
    </svg>
  );
}

export function MBArchiveView({
  reports,
  loading,
  onOpen,
  onGoToSettings,
}: MBArchiveViewProps) {
  if (loading) {
    return (
      <div
        className="text-sm"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        Loading briefings…
      </div>
    );
  }
  if (reports.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center text-center py-12 gap-3"
        data-testid="mb-archive-empty"
      >
        <SunIcon size={40} />
        <p
          className="text-sm"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          No reports yet.
        </p>
        {onGoToSettings && (
          <button
            type="button"
            onClick={onGoToSettings}
            className="text-sm underline"
            data-testid="mb-empty-go-to-settings"
          >
            {"⚙ Go to Settings"}
          </button>
        )}
      </div>
    );
  }
  const groups = groupReports(reports, new Date());
  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <section key={g.key}>
          <h3
            className="text-sm font-semibold mb-2"
            style={{ color: "var(--color-text-tertiary)" }}
            data-testid={`mb-archive-group-${g.key}`}
          >
            {g.heading}
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {g.reports.map((r) => (
              <MBReportCard key={r.id} report={r} onOpen={onOpen} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
