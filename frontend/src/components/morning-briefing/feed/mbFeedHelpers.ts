import type { MbRunSummary } from "../../../api/morning-briefing";

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
  return ts >= start && ts < startOfTodayLocal(now);
}

export function searchReports(
  reports: MbRunSummary[],
  search: string,
): MbRunSummary[] {
  const q = search.trim().toLowerCase();
  if (!q) return reports;
  return reports.filter(
    (r) =>
      (r.subject ?? "").toLowerCase().includes(q) ||
      (r.highlights?.subtitle ?? "").toLowerCase().includes(q),
  );
}

export interface MbFeedGroups {
  today: MbRunSummary[];
  thisWeek: MbRunSummary[];
  older: MbRunSummary[];
}

export function groupReports(
  reports: MbRunSummary[],
  now: Date = new Date(),
): MbFeedGroups {
  const today: MbRunSummary[] = [];
  const thisWeek: MbRunSummary[] = [];
  const older: MbRunSummary[] = [];
  for (const r of reports) {
    if (isToday(r.created_at, now)) today.push(r);
    else if (isWithinLastWeek(r.created_at, now)) thisWeek.push(r);
    else older.push(r);
  }
  return { today, thisWeek, older };
}
