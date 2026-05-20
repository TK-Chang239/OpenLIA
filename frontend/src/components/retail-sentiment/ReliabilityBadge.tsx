import { useTranslation } from "react-i18next";

import type { ReliabilityTier } from "../../lib/retail-sentiment/metric-catalog";

const TIER_KEY: Record<ReliabilityTier, string> = {
  high: "retail_sentiment.reliability.high",
  medium: "retail_sentiment.reliability.med",
  low: "retail_sentiment.reliability.low",
  experimental: "retail_sentiment.reliability.exp",
};

const TIER_TONE: Record<ReliabilityTier, string> = {
  high: "var(--color-feedback-success)",
  medium: "var(--color-feedback-warning)",
  low: "var(--color-feedback-error)",
  experimental: "var(--color-text-tertiary)",
};

export function ReliabilityBadge({ tier }: { tier: ReliabilityTier }) {
  const { t } = useTranslation();
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
      {t(TIER_KEY[tier])}
    </span>
  );
}
