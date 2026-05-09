import { ArrowRight, Download } from "lucide-react";

import type { RecentReport } from "../../api/morning-briefing";
import { reportPdfUrl } from "../../api/reports";
import { DEMO_BRIEFING_META } from "../../lib/morning-briefing/demo-data";

interface Props {
  report: RecentReport;
  onOpen: (report: RecentReport) => void;
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

function deriveSlot(report: RecentReport) {
  const meta = DEMO_BRIEFING_META[report.id];
  if (meta) return meta;
  const hour = new Date(report.created_at).getHours();
  return hour >= 12 ? FALLBACK_POST : FALLBACK_PRE;
}

function formatStamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const date = d.toLocaleDateString(undefined, {
    weekday: "long",
    month: "long",
    day: "numeric",
  });
  return date;
}

export function MBHeroCard({ report, onOpen }: Props) {
  const slot = deriveSlot(report);
  const summary = DEMO_BRIEFING_META[report.id]?.summary;

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
      className="rounded-[12px] border bg-[--color-bg-elevated] p-7 flex flex-col gap-4 cursor-pointer transition-[border-color,box-shadow] duration-[--duration-normal] hover:border-[--color-border-secondary] hover:shadow-md"
      style={{ borderColor: "var(--color-border-subtle)" }}
      role="button"
      tabIndex={0}
      onClick={() => onOpen(report)}
      onKeyDown={(e) => {
        if (e.key === "Enter") onOpen(report);
      }}
      aria-label={`Open ${report.title}`}
      data-testid="mb-hero-card"
    >
      <div className="flex items-center gap-2.5 flex-wrap">
        <span
          className="font-mono text-[10px] tracking-[0.14em] uppercase flex items-center gap-2"
          style={{ color: "var(--color-feedback-success)" }}
        >
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{
              background: "var(--color-accent-primary)",
              boxShadow: "0 0 0 4px rgba(212,255,0,0.18)",
            }}
          />
          Latest briefing
        </span>
        <span
          className="font-mono text-[10px] tracking-[0.1em] uppercase rounded px-2 py-0.5 border"
          style={pillTone}
        >
          {slot.slotLabel}
        </span>
        <span
          className="font-mono text-[10px] tracking-[0.08em]"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {slot.scheduleTime}
        </span>
      </div>
      <div className="flex flex-col gap-2">
        <h2 className="text-[24px] font-medium tracking-[-0.01em] leading-[1.2] m-0 text-[--color-text-primary]">
          {report.title}
        </h2>
        <p
          className="text-[13.5px] m-0"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {formatStamp(report.created_at)}
        </p>
      </div>
      {summary ? (
        <p
          className="text-[15px] leading-[1.6] m-0 max-w-[760px]"
          style={{ color: "var(--color-text-secondary)" }}
        >
          {summary}
        </p>
      ) : null}
      <div className="flex items-center gap-2 mt-1">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onOpen(report);
          }}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md text-[13.5px] font-medium border border-[--color-text-primary] bg-[--color-text-primary] text-[--color-bg-base] hover:bg-black"
          data-testid="mb-hero-open"
        >
          Open briefing
          <ArrowRight size={14} />
        </button>
        <a
          href={reportPdfUrl(report.id)}
          download
          onClick={(e) => e.stopPropagation()}
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md text-[13.5px] border border-[--color-border-secondary] text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong]"
          data-testid="mb-hero-download"
        >
          <Download size={14} />
          Download
        </a>
      </div>
    </article>
  );
}
