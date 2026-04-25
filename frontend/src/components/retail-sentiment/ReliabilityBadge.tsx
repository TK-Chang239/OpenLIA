import type { ReliabilityTier } from "../../lib/retail-sentiment/metric-catalog";

const TIER_LABEL: Record<ReliabilityTier, string> = {
  high: "High",
  medium: "Med",
  low: "Low",
  experimental: "Exp",
};

const TIER_CLASS: Record<ReliabilityTier, string> = {
  high: "bg-[--color-feedback-success-bg] text-[--color-feedback-success]",
  medium: "bg-[--color-feedback-warning-bg] text-[--color-feedback-warning]",
  low: "bg-[--color-feedback-error-bg] text-[--color-feedback-error]",
  experimental: "bg-[--color-bg-elevated] text-[--color-text-secondary]",
};

export function ReliabilityBadge({ tier }: { tier: ReliabilityTier }) {
  return (
    <span
      data-testid={`reliability-${tier}`}
      className={[
        "rounded-full px-2 py-[1px] text-[10px] font-medium uppercase tracking-wide",
        TIER_CLASS[tier],
      ].join(" ")}
    >
      {TIER_LABEL[tier]}
    </span>
  );
}
