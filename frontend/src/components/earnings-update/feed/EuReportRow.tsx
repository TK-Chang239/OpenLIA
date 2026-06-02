import { ChevronRight, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { RunSummary } from "../../../api/earnings-update";

import { tickerOf } from "./feedHelpers";
import { MetricChip, RatingPill } from "./highlightBits";

interface Props {
  report: RunSummary;
  onOpen: (id: string) => void;
  onRemove?: (id: string) => void;
}

function formatTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d
    .toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    })
    .replace(/^0/, "");
}

function formatDateShort(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export function EuReportRow({ report, onOpen, onRemove }: Props) {
  const { t } = useTranslation();
  const ticker = tickerOf(report) || "—";
  const sameDay = (() => {
    const d = new Date(report.created_at);
    if (Number.isNaN(d.getTime())) return false;
    const now = new Date();
    return (
      d.getFullYear() === now.getFullYear() &&
      d.getMonth() === now.getMonth() &&
      d.getDate() === now.getDate()
    );
  })();
  const stamp = sameDay
    ? `${formatTime(report.created_at)} ET`
    : formatDateShort(report.created_at);

  return (
    <div className="relative group">
      <button
        type="button"
        onClick={() => onOpen(report.report_id)}
        data-testid="eu-report-row"
        className="group text-left grid grid-cols-[64px_1fr_auto_30px] gap-4 items-center px-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-feedback-success] hover:-translate-y-0.5 transition-all duration-[--duration-normal] w-full"
      >
        <div className="font-mono text-[13px] font-semibold text-[--color-text-primary] tracking-wide">
          {ticker}
          <span className="block font-mono text-[9.5px] text-[--color-text-tertiary] mt-0.5 tracking-[0.06em] font-medium">
            {stamp}
          </span>
        </div>
        <div className="min-w-0">
          <p className="text-[14.5px] font-medium text-[--color-text-primary] m-0 leading-tight line-clamp-2">
            {report.subject}
          </p>
          {report.highlights?.subtitle ? (
            <p
              data-testid="eu-row-subtitle"
              className="text-[12.5px] text-[--color-text-secondary] m-0 mt-0.5 leading-snug line-clamp-1"
            >
              {report.highlights.subtitle}
            </p>
          ) : null}
        </div>
        {report.highlights && (report.highlights.metrics.length > 0 || report.highlights.rating) ? (
          <div className="hidden sm:flex items-center gap-2 justify-end">
            {report.highlights.metrics.slice(0, 2).map((metric, i) => (
              <MetricChip key={`${metric.label}-${i}`} metric={metric} />
            ))}
            {report.highlights.rating ? <RatingPill rating={report.highlights.rating} /> : null}
          </div>
        ) : (
          <div />
        )}
        <ChevronRight
          size={16}
          className="text-[--color-text-tertiary] group-hover:text-[--color-feedback-success] group-hover:translate-x-[3px] transition-all duration-[--duration-normal]"
        />
      </button>
      {onRemove ? (
        <button
          type="button"
          onClick={() => onRemove(report.report_id)}
          aria-label={t("earnings.feed.remove_aria")}
          className="absolute top-2 right-2 z-10 inline-flex h-6 w-6 items-center justify-center rounded-md bg-[--color-bg-elevated] text-[--color-text-tertiary] opacity-0 group-hover:opacity-100 focus:opacity-100 hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-[opacity,color] duration-[--duration-normal]"
        >
          <Trash2 size={13} />
        </button>
      ) : null}
    </div>
  );
}
