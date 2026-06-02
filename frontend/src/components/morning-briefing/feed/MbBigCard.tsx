import { FileText, Trash2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MbCardHighlights } from "../../../api/morning-briefing";

import { MetricChip, RatingPill } from "./mbHighlightBits";

interface Props {
  title: string;
  subtitle?: string;
  stamp?: string;
  status: "streaming" | "complete";
  reportId?: string | null;
  highlights?: MbCardHighlights | null;
  onOpen?: (id: string) => void;
  onRemove?: (id: string) => void;
}

export function MbBigCard({
  title,
  subtitle,
  stamp,
  status,
  reportId,
  highlights,
  onOpen,
  onRemove,
}: Props) {
  const { t } = useTranslation();
  const live = status === "streaming";
  const resolvedSubtitle = subtitle ?? highlights?.subtitle ?? undefined;
  const metrics = highlights?.metrics?.slice(0, 4) ?? [];
  return (
    <article
      data-testid="mb-big-card"
      className="bg-[--color-bg-elevated] border rounded-[12px] overflow-hidden relative transition-all duration-[--duration-normal] border-[rgba(var(--color-accent-primary-rgb),0.4)] hover:border-[--color-accent-primary] hover:-translate-y-0.5"
    >
      <span className="absolute left-0 top-0 bottom-0 w-[3px] bg-[--color-accent-primary]" />
      {!live && reportId && onRemove ? (
        <button
          type="button"
          onClick={() => onRemove(reportId)}
          aria-label={t("morning_briefing.feed.remove_aria")}
          className="absolute top-3 right-3 z-10 inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-tertiary] hover:text-[--color-feedback-error] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-normal]"
        >
          <Trash2 size={14} />
        </button>
      ) : null}
      <div className="px-[26px] py-5 flex flex-col gap-3">
        <div className="flex items-center gap-2.5 flex-wrap">
          <span className="inline-flex items-center gap-1.5 h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.1em] uppercase text-[--color-feedback-success]">
            {t("morning_briefing.feed.today")}
          </span>
          {stamp ? (
            <span className="font-mono text-[10.5px] tracking-[0.06em] text-[--color-text-tertiary]">
              {stamp}
            </span>
          ) : null}
          {highlights?.rating ? (
            <RatingPill rating={highlights.rating} />
          ) : null}
        </div>
        <h2 className="text-[24px] font-semibold tracking-[-0.01em] m-0 text-[--color-text-primary] leading-[1.2]">
          {title}
        </h2>
        {resolvedSubtitle ? (
          <p className="text-[14.5px] text-[--color-text-secondary] leading-[1.5] m-0">
            {resolvedSubtitle}
          </p>
        ) : null}
        {metrics.length > 0 ? (
          <div className="flex flex-wrap gap-2 mt-0.5">
            {metrics.map((metric, i) => (
              <MetricChip key={`${metric.label}-${i}`} metric={metric} />
            ))}
          </div>
        ) : null}
        <div className="flex gap-2 mt-1">
          {reportId && onOpen ? (
            <button
              type="button"
              onClick={() => onOpen(reportId)}
              className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
            >
              <FileText size={13} /> {t("morning_briefing.feed.open_briefing")}
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 h-8 px-3.5 rounded-md border border-[--color-border-subtle] text-[--color-text-secondary] text-[13px]">
              <span className="w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] animate-live-pulse" />
              {t("morning_briefing.feed.generating")}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}
