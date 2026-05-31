import type { RunSummary } from "../../../api/earnings-update";

const DAY_MS = 24 * 60 * 60 * 1000;

export function startOfTodayLocal(now: Date = new Date()): number {
  const d = new Date(now);
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

export function isToday(iso: string, now: Date = new Date()): boolean {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  return ts >= startOfTodayLocal(now);
}

export function isWithinLastWeek(iso: string, now: Date = new Date()): boolean {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  const start = startOfTodayLocal(now) - 6 * DAY_MS;
  return ts >= start;
}

export function tickerOf(report: RunSummary): string {
  return (report.ticker ?? "").toUpperCase();
}

export function searchReports(reports: RunSummary[], search: string): RunSummary[] {
  const q = search.trim().toUpperCase();
  if (!q) return reports;
  return reports.filter(
    (r) => tickerOf(r).includes(q) || (r.subject ?? "").toUpperCase().includes(q),
  );
}

export interface FeedGroups {
  today: RunSummary[];
  earlierThisWeek: RunSummary[];
}

export function groupReports(
  reports: RunSummary[],
  now: Date = new Date(),
): FeedGroups {
  const today: RunSummary[] = [];
  const earlierThisWeek: RunSummary[] = [];
  for (const r of reports) {
    if (isToday(r.created_at, now)) today.push(r);
    else if (isWithinLastWeek(r.created_at, now)) earlierThisWeek.push(r);
  }
  return { today, earlierThisWeek };
}
