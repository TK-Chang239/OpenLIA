import { FileText } from "lucide-react";

import type { DemoReportMeta } from "../../../lib/earnings-update/demo-data";

interface Props {
  ticker: string;
  title: string;
  subtitle?: string;
  stamp?: string;
  status: "streaming" | "complete";
  reportId?: string | null;
  onOpen?: (id: string) => void;
  meta?: DemoReportMeta;
}

export function EuBigCard({
  ticker,
  title,
  subtitle,
  stamp,
  status,
  reportId,
  onOpen,
  meta,
}: Props) {
  const live = status === "streaming";
  return (
    <article
      data-testid="eu-big-card"
      className="grid grid-cols-1 md:grid-cols-[1fr_280px] gap-0 bg-[--color-bg-elevated] border rounded-[12px] overflow-hidden relative transition-all duration-[--duration-normal] border-[rgba(var(--color-accent-primary-rgb),0.4)] hover:border-[--color-accent-primary] hover:-translate-y-0.5"
    >
      <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-[--color-accent-primary]" />
      <div className="px-[26px] py-5 flex flex-col gap-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          {live ? (
            <span className="inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success]">
              <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
              Call Live
            </span>
          ) : (
            <span className="inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success]">
              Today
            </span>
          )}
          <span className="font-mono text-[10.5px] tracking-[0.06em] text-[--color-text-tertiary] uppercase">
            {ticker}
            {stamp ? (
              <span className="text-[--color-text-tertiary] normal-case">
                {" · "}
                {stamp}
              </span>
            ) : null}
          </span>
        </div>
        <h2 className="text-[24px] font-semibold tracking-[-0.01em] m-0 text-[--color-text-primary] leading-[1.2]">
          {title}
        </h2>
        {subtitle ? (
          <p className="text-[14.5px] text-[--color-text-secondary] leading-[1.5] m-0">
            {subtitle}
          </p>
        ) : null}
        <div className="flex gap-2 mt-1">
          {reportId && onOpen ? (
            <button
              type="button"
              onClick={() => onOpen(reportId)}
              className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
            >
              <FileText size={13} /> Open update
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] text-[13px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
              Generating...
            </span>
          )}
        </div>
      </div>
      <aside className="bg-[--color-accent-subtle] border-t md:border-t-0 md:border-l border-[--color-border-subtle] px-4 py-4 flex flex-col gap-2.5">
        <div className="grid grid-cols-2 gap-x-3.5 gap-y-2.5">
          <SideStat
            label="Rev. surprise"
            value={meta?.revSurprise ?? "—"}
            tone={meta ? (meta.revPositive ? "pos" : "neg") : undefined}
          />
          <SideStat
            label="EPS surprise"
            value={meta?.epsSurprise ?? "—"}
            tone={meta ? (meta.epsPositive ? "pos" : "neg") : undefined}
          />
          <SideStat
            label="After-hours"
            value={meta?.afterHours ?? "—"}
            tone={
              meta?.afterHours !== undefined
                ? meta.afterHoursPositive
                  ? "pos"
                  : "neg"
                : undefined
            }
          />
          <SideStat label="Lia signal" value={meta?.liaSignal ?? "—"} />
        </div>
      </aside>
    </article>
  );
}

function SideStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg";
}) {
  const toneClass =
    tone === "pos"
      ? "text-[--color-feedback-success]"
      : tone === "neg"
        ? "text-[--color-feedback-error]"
        : "text-[--color-text-primary]";
  return (
    <div className="flex flex-col gap-px">
      <span className="font-mono text-[9px] tracking-[0.12em] uppercase text-[--color-text-tertiary]">
        {label}
      </span>
      <span
        className={`font-mono text-[14px] tabular-nums ${toneClass}`}
      >
        {value}
      </span>
    </div>
  );
}
