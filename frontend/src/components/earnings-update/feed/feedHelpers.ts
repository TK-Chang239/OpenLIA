import type { RecentReport } from "../../../api/earnings-update";
import type { WatchlistEntry } from "../../../api/earnings-update";

export type FeedFilter =
  | "all"
  | "watchlist"
  | "portfolio"
  | "beats"
  | "misses";

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

export function isWithinLastWeek(
  iso: string,
  now: Date = new Date(),
): boolean {
  const ts = new Date(iso).getTime();
  if (Number.isNaN(ts)) return false;
  const start = startOfTodayLocal(now) - 6 * DAY_MS;
  return ts >= start;
}

export function tickerOf(report: RecentReport): string {
  return (report.subject ?? "").toUpperCase();
}

interface FilterContext {
  watchlist: WatchlistEntry[];
  search: string;
}

export function applyFilter(
  reports: RecentReport[],
  filter: FeedFilter,
  ctx: FilterContext,
): RecentReport[] {
  const watchTickers = new Set(
    ctx.watchlist.map((w) => w.ticker.toUpperCase()),
  );
  const search = ctx.search.trim().toUpperCase();
  return reports.filter((r) => {
    const t = tickerOf(r);
    if (search && !t.includes(search)) return false;
    switch (filter) {
      case "all":
        return true;
      case "watchlist":
        return watchTickers.has(t);
      case "portfolio":
      case "beats":
      case "misses":
        return false;
    }
  });
}

export interface FeedGroups {
  today: RecentReport[];
  earlierThisWeek: RecentReport[];
}

export function groupReports(
  reports: RecentReport[],
  now: Date = new Date(),
): FeedGroups {
  const today: RecentReport[] = [];
  const earlierThisWeek: RecentReport[] = [];
  for (const r of reports) {
    if (isToday(r.created_at, now)) today.push(r);
    else if (isWithinLastWeek(r.created_at, now)) earlierThisWeek.push(r);
  }
  return { today, earlierThisWeek };
}
