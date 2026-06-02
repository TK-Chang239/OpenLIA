import type { MbCoverMetric } from "../../../api/morning-briefing";

export function toneClass(tone: string | null | undefined): string {
  if (tone === "positive") return "text-[--color-feedback-success]";
  if (tone === "negative") return "text-[--color-feedback-error]";
  return "text-[--color-text-secondary]";
}

export function MetricChip({ metric }: { metric: MbCoverMetric }) {
  return (
    <span
      data-testid="mb-metric-chip"
      className="inline-flex items-baseline gap-1.5 px-2 py-1 rounded-md bg-[--color-surface-hover] border border-[--color-border-subtle]"
    >
      <span className="font-mono text-[9.5px] tracking-[0.06em] uppercase text-[--color-text-tertiary]">
        {metric.label}
      </span>
      <span className="text-[12.5px] font-semibold text-[--color-text-primary] tabular-nums">
        {metric.value}
      </span>
      {metric.change ? (
        <span
          className={`font-mono text-[10.5px] tabular-nums ${toneClass(metric.tone)}`}
        >
          {metric.change}
        </span>
      ) : null}
    </span>
  );
}

export function RatingPill({ rating }: { rating: string }) {
  return (
    <span
      data-testid="mb-rating-pill"
      className="inline-flex items-center h-[22px] px-2.5 rounded bg-[--color-accent-subtle] font-mono text-[10px] tracking-[0.08em] uppercase text-[--color-feedback-success] font-semibold"
    >
      {rating}
    </span>
  );
}
