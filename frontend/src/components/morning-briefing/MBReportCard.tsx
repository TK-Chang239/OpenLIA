import { useState } from "react";
import { ArrowRight, Download } from "lucide-react";

import type { RecentReport } from "../../api/morning-briefing";
import { reportPdfUrl } from "../../api/reports";
import { DEMO_BRIEFING_META } from "../../lib/morning-briefing/demo-data";

interface MBReportCardProps {
  report: RecentReport;
  onOpen: (report: RecentReport) => void;
  now?: Date;
}

const FALLBACK_PRE = {
  slot: "pre_market" as const,
  slotLabel: "Pre-Market",
  scheduleTime: "7:00 AM ET",
};
const FALLBACK_POST = {
  slot: "post_market" as const,
  slotLabel: "Post-Market",
  scheduleTime: "4:30 PM ET",
};

function isWithinHour(createdAt: string, now: Date): boolean {
  const t = new Date(createdAt).getTime();
  return now.getTime() - t < 60 * 60 * 1000;
}

function deriveSlot(report: RecentReport) {
  const meta = DEMO_BRIEFING_META[report.id];
  if (meta) return meta;
  const hour = new Date(report.created_at).getHours();
  return hour >= 12 ? FALLBACK_POST : FALLBACK_PRE;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function MBReportCard({ report, onOpen, now }: MBReportCardProps) {
  const [opened, setOpened] = useState(false);
  const reference = now ?? new Date();
  const fresh = isWithinHour(report.created_at, reference);
  const showNew = fresh && !opened;
  const slot = deriveSlot(report);
  const summary = DEMO_BRIEFING_META[report.id]?.summary;

  const handleOpen = () => {
    setOpened(true);
    onOpen(report);
  };

  const pillTone =
    slot.slot === "pre_market"
      ? {
          color: "var(--color-feedback-success)",
          borderColor: "rgba(107,130,0,0.3)",
          background: "rgba(107,130,0,0.06)",
        }
      : {
          color: "var(--color-feedback-warning)",
          borderColor: "rgba(220,150,20,0.3)",
          background: "rgba(220,150,20,0.06)",
        };

  return (
    <article
      className="relative rounded-[10px] border bg-[--color-bg-elevated] p-4 flex flex-col gap-1.5 cursor-pointer transition-[border-color,box-shadow] duration-[--duration-normal] hover:border-[--color-border-secondary] hover:shadow-sm"
      style={{ borderColor: "var(--color-border-subtle)" }}
      data-testid="mb-report-card"
      onClick={handleOpen}
      onKeyDown={(e) => {
        if (e.key === "Enter") handleOpen();
      }}
      tabIndex={0}
      role="button"
      aria-label={`Open ${report.title}`}
    >
      {showNew ? (
        <span
          data-testid="mb-report-new-badge"
          className="absolute top-3 right-3 font-mono text-[9.5px] font-semibold tracking-[0.05em] uppercase rounded-full px-2 py-0.5 animate-mb-badge-pulse"
          style={{
            background: "var(--color-accent-primary)",
            color: "var(--color-accent-on)",
          }}
        >
          New
        </span>
      ) : null}
      <div className="flex items-center gap-2 text-[13px] font-medium text-[--color-text-secondary]">
        <span>{slot.scheduleTime}</span>
        <span
          className="font-mono text-[9.5px] tracking-[0.1em] uppercase rounded px-2 py-0.5 border"
          style={pillTone}
        >
          {slot.slotLabel}
        </span>
      </div>
      <h4 className="text-[16px] font-semibold m-0 mt-0.5 text-[--color-text-primary]">
        {report.title}
      </h4>
      <div className="text-[13px] text-[--color-text-secondary]">
        {formatDate(report.created_at)}
      </div>
      {summary ? (
        <p
          className="text-[12.5px] leading-[1.5] text-[--color-text-secondary] m-0 mt-1 pt-2 border-t"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
          {summary}
        </p>
      ) : null}
      <div className="flex items-center gap-2 mt-1.5">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            handleOpen();
          }}
          className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-[13px] font-medium border border-[--color-text-primary] bg-[--color-text-primary] text-[--color-bg-base] hover:bg-black"
          data-testid="mb-report-open"
        >
          Open
          <ArrowRight size={13} />
        </button>
        <a
          href={reportPdfUrl(report.id)}
          download
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 h-7 px-3 rounded-md text-[13px] border border-[--color-border-secondary] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
          data-testid="mb-report-download"
        >
          <Download size={13} />
          Download
        </a>
      </div>
    </article>
  );
}
