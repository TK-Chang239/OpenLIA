import { ChevronRight } from "lucide-react";

import type { RunSummary } from "../../../api/earnings-update";

import { tickerOf } from "./feedHelpers";

interface Props {
  report: RunSummary;
  onOpen: (id: string) => void;
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

export function EuReportRow({ report, onOpen }: Props) {
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
    <button
      type="button"
      onClick={() => onOpen(report.report_id)}
      data-testid="eu-report-row"
      className="group text-left grid grid-cols-[64px_1fr_30px] gap-4 items-center px-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-feedback-success] hover:-translate-y-0.5 transition-all duration-[--duration-normal] w-full"
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
      </div>
      <ChevronRight
        size={16}
        className="text-[--color-text-tertiary] group-hover:text-[--color-feedback-success] group-hover:translate-x-[3px] transition-all duration-[--duration-normal]"
      />
    </button>
  );
}
