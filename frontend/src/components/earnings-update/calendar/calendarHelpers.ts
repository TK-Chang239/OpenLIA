import type {
  EuScheduleEntry,
  ReleaseTiming,
  RunSummary,
} from "../../../api/earnings-update";

export const VISIBLE_CHIPS = 3;

export type CalEventStatus = "live" | "reported" | "scheduled" | "failed";
export type CalSession = "am" | "pm" | "tbd";

export interface CalendarEvent {
  ticker: string;
  status: CalEventStatus;
  session: CalSession;
  dateKey: string;
  reportId: string | null;
  epsEstimate: string | null;
  revenueEstimate: string | null;
  subject: string | null;
}

export interface CalendarCell {
  date: Date;
  dateKey: string;
  inMonth: boolean;
  isToday: boolean;
  isWeekend: boolean;
  events: CalendarEvent[];
}

export interface MonthSummary {
  total: number;
  preMarket: number;
  afterClose: number;
  live: number;
}

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

export function toDateKey(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

// The backend stores fiscal_date as a plain calendar-date string ("YYYY-MM-DD",
// no time component), so slicing the date portion yields that calendar date with
// no timezone shift. Grid cells are keyed by toDateKey() of a local Date, so a
// plain "YYYY-MM-DD" lands on the same cell regardless of the viewer's timezone.
// (Defensive slice in case a future source ever sends an ISO datetime.)
function normaliseDateKey(raw: string): string {
  return raw.slice(0, 10);
}

export function sessionFromTiming(timing: ReleaseTiming): CalSession {
  if (timing === "pre_market") return "am";
  if (timing === "post_market") return "pm";
  return "tbd";
}

const STATUS_RANK: Record<CalEventStatus, number> = {
  live: 0,
  reported: 1,
  scheduled: 2,
  failed: 3,
};

function runStatusToEvent(status: RunSummary["status"]): CalEventStatus {
  if (status === "running") return "live";
  if (status === "failed") return "failed";
  return "reported";
}

export function buildEventMap(
  schedule: EuScheduleEntry[],
  runs: RunSummary[],
): Map<string, CalendarEvent[]> {
  // Collect per date, deduping by ticker keeping the higher-precedence event.
  const byDate = new Map<string, Map<string, CalendarEvent>>();

  function put(dateKey: string, event: CalendarEvent): void {
    let perTicker = byDate.get(dateKey);
    if (!perTicker) {
      perTicker = new Map();
      byDate.set(dateKey, perTicker);
    }
    const existing = perTicker.get(event.ticker);
    if (!existing || STATUS_RANK[event.status] < STATUS_RANK[existing.status]) {
      perTicker.set(event.ticker, event);
    }
  }

  for (const s of schedule) {
    // Only pending (not-yet-run) releases are placed as "scheduled". A reported
    // schedule row is already represented by its run record; skipped is dropped.
    if (s.status !== "pending") continue;
    if (!s.fiscal_date) continue;
    const dateKey = normaliseDateKey(s.fiscal_date);
    put(dateKey, {
      ticker: s.ticker.toUpperCase(),
      status: "scheduled",
      session: sessionFromTiming(s.release_timing),
      dateKey,
      reportId: s.report_id,
      epsEstimate: s.eps_estimate,
      revenueEstimate: s.revenue_estimate,
      subject: null,
    });
  }

  for (const r of runs) {
    if (!r.fiscal_date) continue;
    const dateKey = normaliseDateKey(r.fiscal_date);
    put(dateKey, {
      ticker: r.ticker.toUpperCase(),
      status: runStatusToEvent(r.status),
      session: "tbd", // runs carry no release timing
      dateKey,
      reportId: r.report_id,
      epsEstimate: null,
      revenueEstimate: null,
      subject: r.subject,
    });
  }

  const result = new Map<string, CalendarEvent[]>();
  for (const [dateKey, perTicker] of byDate) {
    const events = [...perTicker.values()].sort((a, b) => {
      const rank = STATUS_RANK[a.status] - STATUS_RANK[b.status];
      if (rank !== 0) return rank;
      return a.ticker.localeCompare(b.ticker);
    });
    result.set(dateKey, events);
  }
  return result;
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

export function buildMonthCells(
  year: number,
  month: number,
  eventMap: Map<string, CalendarEvent[]>,
  today: Date,
): CalendarCell[] {
  const first = new Date(year, month, 1);
  const start = new Date(year, month, 1 - first.getDay());
  const cells: CalendarCell[] = [];
  for (let i = 0; i < 42; i++) {
    const date = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i);
    const dateKey = toDateKey(date);
    const day = date.getDay();
    cells.push({
      date,
      dateKey,
      inMonth: date.getMonth() === month,
      isToday: sameDay(date, today),
      isWeekend: day === 0 || day === 6,
      events: eventMap.get(dateKey) ?? [],
    });
  }
  return cells;
}

export function summarizeMonth(cells: CalendarCell[]): MonthSummary {
  let total = 0;
  let preMarket = 0;
  let afterClose = 0;
  let live = 0;
  for (const cell of cells) {
    if (!cell.inMonth) continue;
    for (const e of cell.events) {
      total++;
      if (e.session === "am") preMarket++;
      if (e.session === "pm") afterClose++;
      if (e.status === "live") live++;
    }
  }
  return { total, preMarket, afterClose, live };
}
