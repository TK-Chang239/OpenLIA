import { useEffect } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { CalendarEvent } from "./calendarHelpers";

interface Props {
  dateKey: string | null;
  events: CalendarEvent[];
  onClose: () => void;
  onOpenReport: (reportId: string) => void;
}

function formatDayHeading(dateKey: string, locale: string): string {
  const [y, m, d] = dateKey.split("-").map(Number);
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString(locale, {
    weekday: "long",
    month: "short",
    day: "numeric",
  });
}

export function EuCalendarDayPopover({ dateKey, events, onClose, onOpenReport }: Props) {
  const { t, i18n } = useTranslation();

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (dateKey) window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [dateKey, onClose]);

  if (!dateKey) return null;

  const count = events.length;
  const countLabel =
    count === 1
      ? t("earnings.calendar.pop_reports_one", { count })
      : t("earnings.calendar.pop_reports_other", { count });

  return (
    <>
      <div
        className="fixed inset-0 z-[60] bg-black/30"
        onClick={onClose}
        aria-hidden
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={formatDayHeading(dateKey, i18n.language)}
        className="fixed z-[61] left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[min(440px,92vw)] max-h-[80vh] overflow-y-auto bg-[--color-bg-elevated] border border-[--color-border-secondary] rounded-[12px] shadow-xl"
      >
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-3 border-b border-[--color-border-subtle]">
          <div>
            <span className="font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-text-tertiary]">
              {formatDayHeading(dateKey, i18n.language)}
            </span>
            <h3 className="text-[16px] font-semibold text-[--color-text-primary] m-0 mt-0.5">
              {countLabel}
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("earnings.calendar.close")}
            className="text-[--color-text-tertiary] hover:text-[--color-text-primary]"
          >
            <X size={18} />
          </button>
        </header>
        <div className="p-3 flex flex-col gap-2">
          {count === 0 ? (
            <p className="font-mono text-[11px] tracking-[0.1em] uppercase text-[--color-text-tertiary] text-center py-5">
              {t("earnings.calendar.pop_empty")}
            </p>
          ) : (
            events.map((e) => (
              <DayRow key={`${e.ticker}-${e.dateKey}`} event={e} onOpenReport={onOpenReport} />
            ))
          )}
        </div>
      </div>
    </>
  );
}

function DayRow({
  event,
  onOpenReport,
}: {
  event: CalendarEvent;
  onOpenReport: (reportId: string) => void;
}) {
  const { t } = useTranslation();
  const sessionLabel =
    event.session === "am"
      ? t("earnings.calendar.pop_pre_market")
      : event.session === "pm"
        ? t("earnings.calendar.pop_after_close")
        : null;
  const openable = (event.status === "reported" || event.status === "live") && event.reportId;

  const inner = (
    <>
      <span className="font-mono text-[13px] font-semibold text-[--color-text-primary] w-[56px] shrink-0">
        {event.ticker}
      </span>
      <div className="min-w-0 flex-1">
        {event.subject ? (
          <p className="text-[13px] text-[--color-text-primary] m-0 truncate">
            {event.subject}
          </p>
        ) : null}
        <span className="font-mono text-[10px] tracking-[0.06em] text-[--color-text-tertiary]">
          {event.status === "live"
            ? t("earnings.calendar.pop_status_live")
            : event.status === "reported"
              ? t("earnings.calendar.pop_status_reported")
              : sessionLabel ?? ""}
          {event.epsEstimate || event.revenueEstimate ? (
            <>
              {event.status === "live" ||
              event.status === "reported" ||
              sessionLabel
                ? " · "
                : ""}
              {t("earnings.calendar.pop_est_eps")} {event.epsEstimate ?? "—"} ·{" "}
              {t("earnings.calendar.pop_est_rev")} {event.revenueEstimate ?? "—"}
            </>
          ) : null}
        </span>
      </div>
    </>
  );

  if (openable) {
    return (
      <button
        type="button"
        onClick={() => onOpenReport(event.reportId as string)}
        className="flex items-center gap-3 text-left px-3 py-2.5 rounded-[8px] border border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-feedback-success] transition-colors duration-[--duration-normal]"
      >
        {inner}
      </button>
    );
  }
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-[8px] border border-[--color-border-subtle] bg-[--color-bg-base]">
      {inner}
    </div>
  );
}
