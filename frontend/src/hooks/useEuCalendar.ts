import { useCallback, useMemo, useState } from "react";

import type { EuScheduleEntry, RunSummary } from "../api/earnings-update";
import {
  buildEventMap,
  buildMonthCells,
  summarizeMonth,
  type CalendarCell,
  type CalendarEvent,
  type MonthSummary,
} from "../components/earnings-update/calendar/calendarHelpers";

export interface EuCalendarState {
  viewYear: number;
  viewMonth: number; // 0-indexed
  cells: CalendarCell[];
  summary: MonthSummary;
  eventMap: Map<string, CalendarEvent[]>;
  nextMonth: () => void;
  prevMonth: () => void;
  goToday: () => void;
}

export function useEuCalendar(
  schedule: EuScheduleEntry[],
  runs: RunSummary[],
): EuCalendarState {
  const today = useMemo(() => new Date(), []);
  const [anchor, setAnchor] = useState(
    () => new Date(today.getFullYear(), today.getMonth(), 1),
  );

  const eventMap = useMemo(
    () => buildEventMap(schedule, runs),
    [schedule, runs],
  );

  const cells = useMemo(
    () => buildMonthCells(anchor.getFullYear(), anchor.getMonth(), eventMap, today),
    [anchor, eventMap, today],
  );

  const summary = useMemo(() => summarizeMonth(cells), [cells]);

  const nextMonth = useCallback(() => {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() + 1, 1));
  }, []);
  const prevMonth = useCallback(() => {
    setAnchor((a) => new Date(a.getFullYear(), a.getMonth() - 1, 1));
  }, []);
  const goToday = useCallback(() => {
    setAnchor(new Date(today.getFullYear(), today.getMonth(), 1));
  }, [today]);

  return {
    viewYear: anchor.getFullYear(),
    viewMonth: anchor.getMonth(),
    cells,
    summary,
    eventMap,
    nextMonth,
    prevMonth,
    goToday,
  };
}
