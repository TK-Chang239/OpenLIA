import { ChevronRight } from "lucide-react";

import type { RecentReport } from "../../../api/earnings-update";
import type { DemoReportMeta, Verdict } from "../../../lib/earnings-update/demo-data";

import { tickerOf } from "./feedHelpers";

interface Props {
  report: RecentReport;
  onOpen: (id: string) => void;
  meta?: DemoReportMeta;
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

function verdictClasses(v: Verdict): string {
  switch (v) {
    case "beat":
      return "bg-[rgba(168,204,0,0.10)] border-[rgba(168,204,0,0.30)] text-[--color-feedback-success]";
    case "miss":
      return "bg-[rgba(196,46,46,0.08)] border-[rgba(196,46,46,0.25)] text-[--color-feedback-error]";
    case "mixed":
    default:
      return "bg-[rgba(200,140,40,0.10)] border-[rgba(200,140,40,0.25)] text-[--color-feedback-warning]";
  }
}

export function EuReportRow({ report, onOpen, meta }: Props) {
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
      onClick={() => onOpen(report.id)}
      data-testid="eu-report-row"
      className="group text-left grid grid-cols-[64px_1fr_30px] md:grid-cols-[64px_1fr_180px_180px_30px] gap-4 items-center px-4 py-3.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[10px] hover:border-[--color-feedback-success] hover:-translate-y-0.5 transition-all duration-[--duration-normal] w-full"
    >
      <div className="font-mono text-[13px] font-semibold text-[--color-text-primary] tracking-wide">
        {ticker}
        <span className="block font-mono text-[9.5px] text-[--color-text-tertiary] mt-0.5 tracking-[0.06em] font-medium">
          {stamp}
        </span>
      </div>
      <div className="min-w-0">
        <p className="text-[14.5px] font-medium text-[--color-text-primary] m-0 mb-1 leading-tight line-clamp-2">
          {report.title}
        </p>
        {meta?.summary ? (
          <p className="text-[12.5px] text-[--color-text-secondary] m-0 leading-[1.45] line-clamp-2">
            {meta.summary}
          </p>
        ) : null}
      </div>
      <div className="hidden md:flex flex-col gap-1">
        <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
          Verdict
        </span>
        {meta ? (
          <span
            className={`inline-flex items-center self-start font-mono text-[10px] tracking-[0.06em] uppercase px-2 py-[3px] rounded border ${verdictClasses(meta.verdict)}`}
          >
            {meta.verdictLabel}
          </span>
        ) : (
          <span className="font-mono text-[10.5px] tracking-[0.08em] uppercase text-[--color-text-tertiary] self-start">
            —
          </span>
        )}
      </div>
      <div className="hidden md:grid grid-cols-2 gap-x-3 gap-y-1.5 font-mono text-[11px]">
        <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
          Rev.
        </span>
        <span
          className={`font-mono tabular-nums ${
            meta
              ? meta.revPositive
                ? "text-[--color-feedback-success]"
                : "text-[--color-feedback-error]"
              : "text-[--color-text-tertiary]"
          }`}
        >
          {meta?.revSurprise ?? "—"}
        </span>
        <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
          EPS
        </span>
        <span
          className={`font-mono tabular-nums ${
            meta
              ? meta.epsPositive
                ? "text-[--color-feedback-success]"
                : "text-[--color-feedback-error]"
              : "text-[--color-text-tertiary]"
          }`}
        >
          {meta?.epsSurprise ?? "—"}
        </span>
      </div>
      <ChevronRight
        size={16}
        className="text-[--color-text-tertiary] group-hover:text-[--color-feedback-success] group-hover:translate-x-[3px] transition-all duration-[--duration-normal]"
      />
    </button>
  );
}
