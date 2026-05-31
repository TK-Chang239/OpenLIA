import { useCallback, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Crosshair } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { EuScheduleEntry, RunSummary } from "../../../api/earnings-update";
import { useEuCalendar } from "../../../hooks/useEuCalendar";

import {
  VISIBLE_CHIPS,
  type CalEventStatus,
  type CalendarEvent,
} from "./calendarHelpers";
import { EuCalendarDayPopover } from "./EuCalendarDayPopover";

interface Props {
  schedule: EuScheduleEntry[];
  runs: RunSummary[];
  onOpenReport: (reportId: string) => void;
}

const STATUS_DOT: Record<CalEventStatus, string> = {
  live: "bg-[--color-accent-primary]",
  reported: "bg-[--color-feedback-success]",
  scheduled: "bg-[--color-border-strong]",
  failed: "bg-[--color-feedback-error]",
};

function weekdayShortNames(locale: string): string[] {
  // 2026-03-01 is a Sunday; produce Sun..Sat in the active locale.
  const base = new Date(2026, 2, 1);
  return Array.from({ length: 7 }, (_, i) =>
    new Date(base.getFullYear(), base.getMonth(), base.getDate() + i).toLocaleDateString(
      locale,
      { weekday: "short" },
    ),
  );
}

export function EuCalendar({ schedule, runs, onOpenReport }: Props) {
  const { t, i18n } = useTranslation();
  const {
    viewYear,
    viewMonth,
    cells,
    summary,
    eventMap,
    nextMonth,
    prevMonth,
    goToday,
  } = useEuCalendar(schedule, runs);
  const [openDay, setOpenDay] = useState<string | null>(null);
  const dow = useMemo(() => weekdayShortNames(i18n.language), [i18n.language]);

  const monthLabel = useMemo(
    () =>
      new Date(viewYear, viewMonth, 1).toLocaleDateString(i18n.language, {
        month: "long",
        year: "numeric",
      }),
    [viewYear, viewMonth, i18n.language],
  );

  const openReportFromPopover = useCallback(
    (reportId: string) => {
      setOpenDay(null);
      onOpenReport(reportId);
    },
    [onOpenReport],
  );

  return (
    <div>
      <div className="flex items-center gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label={t("earnings.calendar.prev_month")}
            onClick={prevMonth}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
          >
            <ChevronLeft size={16} />
          </button>
          <button
            type="button"
            aria-label={t("earnings.calendar.next_month")}
            onClick={nextMonth}
            className="inline-flex items-center justify-center w-8 h-8 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
          >
            <ChevronRight size={16} />
          </button>
        </div>
        <h2
          data-testid="eu-cal-month"
          className="text-[20px] font-semibold tracking-[-0.01em] text-[--color-text-primary] m-0 capitalize"
        >
          {monthLabel}
        </h2>
        <button
          type="button"
          onClick={goToday}
          className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border border-[--color-border-subtle] text-[12.5px] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover]"
        >
          <Crosshair size={13} /> {t("earnings.calendar.today")}
        </button>
        <div className="flex-1" />
        <div className="flex gap-5">
          <Summary label={t("earnings.calendar.summary_reports")} value={summary.total} />
          <Summary label={t("earnings.calendar.summary_pre_market")} value={summary.preMarket} />
          <Summary label={t("earnings.calendar.summary_after_close")} value={summary.afterClose} />
          <Summary
            label={t("earnings.calendar.summary_live")}
            value={summary.live}
            tone={summary.live > 0 ? "live" : undefined}
          />
        </div>
      </div>

      <div className="grid grid-cols-7 gap-px mb-1">
        {dow.map((name) => (
          <span
            key={name}
            className="font-mono text-[9.5px] tracking-[0.1em] uppercase text-[--color-text-tertiary] text-center py-1"
          >
            {name}
          </span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-px bg-[--color-border-subtle] border border-[--color-border-subtle] rounded-[10px] overflow-hidden">
        {cells.map((cell) => {
          const visible = cell.events.slice(0, VISIBLE_CHIPS);
          const overflow = cell.events.length - visible.length;
          const clickable = cell.events.length > 0;
          return (
            <div
              key={cell.dateKey}
              data-testid={`eu-cal-cell-${cell.dateKey}`}
              onClick={clickable ? () => setOpenDay(cell.dateKey) : undefined}
              className={`min-h-[92px] p-1.5 flex flex-col gap-1 bg-[--color-bg-elevated] ${
                cell.inMonth ? "" : "opacity-40"
              } ${clickable ? "cursor-pointer hover:bg-[--color-surface-hover]" : ""}`}
            >
              <div className="flex items-center justify-between">
                <span
                  className={`font-mono text-[11px] ${
                    cell.isToday
                      ? "text-[--color-text-primary] font-semibold"
                      : "text-[--color-text-tertiary]"
                  }`}
                >
                  {cell.date.getDate()}
                </span>
                {cell.isToday ? (
                  <span className="font-mono text-[8px] tracking-[0.1em] uppercase px-1 py-0.5 rounded bg-[--color-accent-subtle] text-[--color-feedback-success]">
                    {t("earnings.calendar.today_pill")}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-col gap-0.5">
                {visible.map((e) => (
                  <Chip key={`${e.ticker}-${e.status}`} event={e} />
                ))}
                {overflow > 0 ? (
                  <span className="font-mono text-[9px] text-[--color-text-tertiary] pl-0.5">
                    {t("earnings.calendar.more", { count: overflow })}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-1.5 mt-3">
        <Legend dot={STATUS_DOT.live} label={t("earnings.calendar.legend_live")} />
        <Legend dot={STATUS_DOT.reported} label={t("earnings.calendar.legend_reported")} />
        <Legend dot={STATUS_DOT.scheduled} label={t("earnings.calendar.legend_pre_market")} />
      </div>
      <p className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary] mt-2">
        {t("earnings.calendar.watchlist_only")}
      </p>

      <EuCalendarDayPopover
        dateKey={openDay}
        events={openDay ? eventMap.get(openDay) ?? [] : []}
        onClose={() => setOpenDay(null)}
        onOpenReport={openReportFromPopover}
      />
    </div>
  );
}

function Chip({ event }: { event: CalendarEvent }) {
  const { t } = useTranslation();
  const sessionLabel =
    event.session === "am"
      ? t("earnings.calendar.session_am")
      : event.session === "pm"
        ? t("earnings.calendar.session_pm")
        : "";
  return (
    <span className="flex items-center gap-1 px-1 py-0.5 rounded bg-[--color-bg-base] border border-[--color-border-subtle]">
      <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${STATUS_DOT[event.status]}`} />
      <span className="font-mono text-[9.5px] font-semibold text-[--color-text-primary] truncate">
        {event.ticker}
      </span>
      {sessionLabel ? (
        <span className="font-mono text-[8px] text-[--color-text-tertiary] ml-auto">
          {sessionLabel}
        </span>
      ) : null}
    </span>
  );
}

function Summary({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone?: "live";
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="font-mono text-[9px] tracking-[0.1em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span
        className={`font-mono text-[18px] tabular-nums leading-none ${
          tone === "live" ? "text-[--color-feedback-success]" : "text-[--color-text-primary]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function Legend({ dot, label }: { dot: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[9.5px] tracking-[0.06em] uppercase text-[--color-text-tertiary]">
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {label}
    </span>
  );
}
