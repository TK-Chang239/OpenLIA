/**
 * Single source-of-truth for the 12 Retail Sentiment metrics.
 * Used by `MetricCard`, `MetricsDeepDive`, and `OverviewTab` to drive
 * label/units/formula/reliability rendering.
 */

export type ReliabilityTier = "high" | "medium" | "low" | "experimental";
export type ChartType = "gauge" | "bar" | "line" | "scatter" | "stat";

export interface MetricDefinition {
  id: string;
  number: number;
  label: string;
  units: string;
  formula: string;
  reliability: ReliabilityTier;
  chart: ChartType;
  description: string;
}

export const RS_METRIC_CATALOG: MetricDefinition[] = [
  {
    id: "sentiment_score",
    number: 1,
    label: "Sentiment Score",
    units: "[-1, 1]",
    formula: "mean(label_score) over classified posts",
    reliability: "high",
    chart: "gauge",
    description:
      "Average bullish/bearish polarity across classified posts and articles.",
  },
  {
    id: "buzz_volume",
    number: 2,
    label: "Buzz Volume",
    units: "ratio",
    formula: "count_today / mean(count_30d)",
    reliability: "high",
    chart: "bar",
    description:
      "Today's mention count normalized against the 30-day moving average.",
  },
  {
    id: "sentiment_momentum",
    number: 3,
    label: "Sentiment Momentum",
    units: "Δ score",
    formula: "score_today − score_prior",
    reliability: "high",
    chart: "line",
    description: "Change in sentiment score versus the prior snapshot.",
  },
  {
    id: "bull_bear_ratio",
    number: 4,
    label: "Bull / Bear Ratio",
    units: "ratio",
    formula: "bullish_count / max(bearish_count, 1)",
    reliability: "high",
    chart: "stat",
    description: "Ratio of bullish to bearish classifications.",
  },
  {
    id: "buzz_sentiment_divergence",
    number: 5,
    label: "Buzz / Sentiment Divergence",
    units: "z-score gap",
    formula: "|z(buzz)| − |z(sentiment)|",
    reliability: "medium",
    chart: "line",
    description:
      "Detects when buzz spikes without matching sentiment movement.",
  },
  {
    id: "social_velocity",
    number: 6,
    label: "Social Velocity",
    units: "posts / hr",
    formula: "posts_last_24h / 24",
    reliability: "high",
    chart: "stat",
    description: "Average post rate over the last 24-hour window.",
  },
  {
    id: "cross_source_agreement",
    number: 7,
    label: "Cross-Source Agreement",
    units: "[0, 1]",
    formula: "1 − std(per_source_means)",
    reliability: "medium",
    chart: "gauge",
    description: "How closely sources agree on the polarity call.",
  },
  {
    id: "put_call_ratio",
    number: 8,
    label: "Put / Call Sentiment Ratio",
    units: "ratio",
    formula: "(puts / calls) × (1 − sentiment)",
    reliability: "experimental",
    chart: "stat",
    description:
      "Options-implied bearishness scaled by retail sentiment posture.",
  },
  {
    id: "short_interest_pressure",
    number: 9,
    label: "Short Interest Pressure",
    units: "index",
    formula: "short_pct_float × days_to_cover",
    reliability: "medium",
    chart: "bar",
    description:
      "Squeeze-pressure heuristic from short interest and days-to-cover.",
  },
  {
    id: "narrative_concentration",
    number: 10,
    label: "Narrative Concentration",
    units: "[0, 1]",
    formula: "top3_phrase_share / total_phrases",
    reliability: "medium",
    chart: "stat",
    description:
      "Top-3 key-phrase share — high values mean a single narrative dominates. Requires LLM-backed classifier (NeutralClassifier emits no phrases).",
  },
  {
    id: "institutional_retail_gap",
    number: 11,
    label: "Institutional / Retail Gap",
    units: "Δ pct",
    formula: "institutional_change_pct − retail_sentiment",
    reliability: "experimental",
    chart: "stat",
    description:
      "Gap between institutional flow direction and retail sentiment.",
  },
  {
    id: "event_sensitivity",
    number: 12,
    label: "Event Sensitivity Score",
    units: "stddev",
    formula: "std(daily_returns_30d)",
    reliability: "experimental",
    chart: "line",
    description:
      "Volatility of daily returns over the last 30 trading days. Cold-start when fewer than 30 samples.",
  },
];

export const RS_METRIC_BY_ID: Record<string, MetricDefinition> =
  Object.fromEntries(RS_METRIC_CATALOG.map((m) => [m.id, m]));
