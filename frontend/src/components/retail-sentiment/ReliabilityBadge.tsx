import type { ReliabilityTier } from "../../lib/retail-sentiment/metric-catalog";

const TIER_LABEL: Record<ReliabilityTier, string> = {
  high: "High",
  medium: "Med",
  low: "Low",
  experimental: "Exp",
};

const TIER_TONE: Record<ReliabilityTier, string> = {
  high: "var(--color-feedback-success)",
  medium: "var(--color-feedback-warning)",
  low: "var(--color-feedback-error)",
  experimental: "var(--color-text-tertiary)",
};

export function ReliabilityBadge({ tier }: { tier: ReliabilityTier }) {
  return (
    <span
      data-testid={`reliability-${tier}`}
      className="rs-mono-label"
      style={{
        fontSize: "9px",
        letterSpacing: "0.14em",
        padding: "2px 6px",
        borderRadius: 3,
        color: TIER_TONE[tier],
        background: "var(--color-bg-code)",
        textTransform: "uppercase",
      }}
    >
      {TIER_LABEL[tier]}
    </span>
  );
}
