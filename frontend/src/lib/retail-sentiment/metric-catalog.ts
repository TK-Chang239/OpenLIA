/**
 * Single source-of-truth for the 12 Retail Sentiment metrics.
 * Used by `MetricCard`, `MetricsDeepDiveTab`, `OverviewTab`, `InsightsTab`,
 * and `ReliabilityScatter` to drive label / units / formula / chart-type /
 * reliability / interpretation rendering.
 *
 * Reliability reference values (predictive_strength + timeliness, 0-10) are
 * grounded in the design doc at planning notes / sentiment_dashboard_design.md.
 */

export type ReliabilityTier = "high" | "medium" | "low" | "experimental";
export type ChartType =
  | "gauge"
  | "bar"
  | "line"
  | "area"
  | "stacked-bar"
  | "scatter"
  | "stat";
export type FrameworkQuestion =
  | "mood"
  | "attention"
  | "direction"
  | "conviction"
  | "contrarian"
  | "trust";

export interface MetricDefinition {
  id: string;
  number: number;
  label: string;
  units: string;
  formula: string;
  reliability: ReliabilityTier;
  /** Predictive strength on a 0-10 scale (does this metric forecast price moves?). */
  predictive_strength: number;
  /** Timeliness on a 0-10 scale (how early before price moves does this fire?). */
  timeliness: number;
  chart: ChartType;
  description: string;
  /** What this metric tells you in plain English. */
  interpretation: string;
  /** Caveat or pitfall to remember when reading the value. */
  caveat: string;
  /** Insights-tab grouping question. Null if the metric is supporting / not a primary signal. */
  framework: FrameworkQuestion | null;
  /** Field on `RsSnapshot`. */
  field: string;
}

export const RS_METRIC_CATALOG: MetricDefinition[] = [
  {
    id: "sentiment_score",
    number: 1,
    label: "Sentiment Score",
    units: "[-1, 1]",
    formula: "(positive_mentions − negative_mentions) / total_mentions",
    reliability: "high",
    predictive_strength: 6,
    timeliness: 5,
    chart: "gauge",
    description:
      "Average bullish/bearish polarity across classified posts and articles.",
    interpretation:
      "The current market mood toward a stock as a single number. Near zero means balanced opinion, not absence of opinion.",
    caveat:
      "+0.2 for AAPL is more significant than +0.2 for GME — always compare against the stock's own historical range, not across stocks.",
    framework: "mood",
    field: "sentiment_score",
  },
  {
    id: "buzz_volume",
    number: 2,
    label: "Buzz Volume",
    units: "× 30d avg",
    formula: "count(mentions_today) / mean(mentions_30d)",
    reliability: "high",
    predictive_strength: 3,
    timeliness: 7,
    chart: "bar",
    description:
      "Today's mention count normalized against the 30-day moving average.",
    interpretation:
      "How much people are talking about a stock, independent of bull/bear tone. Spikes coincide with earnings, news, or viral posts.",
    caveat:
      "High buzz predicts volatility (in either direction), not direction. Always pair with sentiment to know which way.",
    framework: "attention",
    field: "buzz_volume",
  },
  {
    id: "sentiment_momentum",
    number: 3,
    label: "Sentiment Momentum",
    units: "Δ score",
    formula: "SMA(sentiment, 5)_today − SMA(sentiment, 5)_yesterday",
    reliability: "high",
    predictive_strength: 7,
    timeliness: 8,
    chart: "area",
    description:
      "Daily change in the 5-day moving average of sentiment score.",
    interpretation:
      "The most useful leading indicator. A stock can have negative sentiment but positive momentum (the mood is recovering). Often leads price by 1-3 days.",
    caveat:
      "Smoothed via 5d SMA so single-day noise is filtered — but also lags abrupt regime changes by ~1 day.",
    framework: "direction",
    field: "sentiment_momentum",
  },
  {
    id: "bull_bear_ratio",
    number: 4,
    label: "Bull / Bear Ratio",
    units: "ratio",
    formula: "bullish_posts / (bullish_posts + bearish_posts)",
    reliability: "high",
    predictive_strength: 5,
    timeliness: 4,
    chart: "stacked-bar",
    description: "Proportion of bullish vs bearish posts (neutral excluded).",
    interpretation:
      "Reveals conviction breadth when paired with buzz: 90/10 from 50 posts = fragile concentrated enthusiasm; 60/40 from 5,000 posts = durable broad optimism.",
    caveat:
      "Neutral posts are excluded — a 50/50 split can mean genuine debate, not lack of interest.",
    framework: "conviction",
    field: "bull_bear_ratio",
  },
  {
    id: "buzz_sentiment_divergence",
    number: 5,
    label: "Buzz / Sentiment Divergence",
    units: "z gap",
    formula: "z_score(buzz_30d) − z_score(sentiment_30d)",
    reliability: "medium",
    predictive_strength: 8,
    timeliness: 6,
    chart: "bar",
    description:
      "Detects when buzz volume and sentiment move in opposite directions.",
    interpretation:
      "Highest predictive-strength metric. >+1.0 = panic (mean-reversion buy signal). <-1.0 = stealth recovery (smart money accumulating quietly).",
    caveat:
      "Divergence in the |0–1.0| band is normal noise. Only act when it crosses ±1.0 thresholds.",
    framework: "contrarian",
    field: "buzz_sentiment_divergence",
  },
  {
    id: "social_velocity",
    number: 6,
    label: "Social Velocity",
    units: "Δ posts %",
    formula: "(buzz_today − buzz_yesterday) / buzz_yesterday",
    reliability: "high",
    predictive_strength: 4,
    timeliness: 9,
    chart: "stat",
    description: "Acceleration of mentions — change rate, not absolute volume.",
    interpretation:
      "Catches trends before buzz peaks. A stock can have normal volume today but velocity +150% — by the time buzz hits 5x, the velocity signal already fired.",
    caveat:
      "Surfaces as Insights alerts only — not charted alongside other metrics, since the signal is the threshold crossing, not the curve.",
    framework: "attention",
    field: "social_velocity",
  },
  {
    id: "cross_source_agreement",
    number: 7,
    label: "Cross-Source Agreement",
    units: "[0, 1]",
    formula: "1 − std(per_source_polarity_means)",
    reliability: "medium",
    predictive_strength: 9,
    timeliness: 5,
    chart: "gauge",
    description: "How closely independent sources agree on the polarity call.",
    interpretation:
      "When EODHD news, X social, and FMP social all agree, the signal is 2-3x more reliable than any single source.",
    caveat:
      "Slow-moving — a high-agreement signal that just appeared is more reliable than one that's been stable for weeks.",
    framework: "trust",
    field: "cross_source_agreement",
  },
  {
    id: "put_call_ratio",
    number: 8,
    label: "Put / Call Sentiment Ratio",
    units: "ratio",
    formula: "(puts / calls) × (1 − sentiment)",
    reliability: "experimental",
    predictive_strength: 5,
    timeliness: 4,
    chart: "stat",
    description:
      "Options-implied bearishness scaled by retail sentiment posture.",
    interpretation:
      "Pairs implied volatility with retail mood. A high P/C ratio when retail is also bullish is a stronger contrarian fade signal than P/C alone.",
    caveat:
      "Requires options data provider (currently optional). Disabled when not configured.",
    framework: "contrarian",
    field: "put_call_ratio",
  },
  {
    id: "short_interest_pressure",
    number: 9,
    label: "Short Interest Pressure",
    units: "index",
    formula: "short_pct_float × days_to_cover",
    reliability: "medium",
    predictive_strength: 5,
    timeliness: 3,
    chart: "bar",
    description:
      "Squeeze-pressure heuristic from short interest and days-to-cover.",
    interpretation:
      "High pressure × rising bull/bear ratio = squeeze setup. Low pressure × bearish flow = trend, not squeeze.",
    caveat:
      "Short data is reported with a 2-week lag in the US — treat as a slow-moving regime indicator, not a tactical trigger.",
    framework: "conviction",
    field: "short_interest_pressure",
  },
  {
    id: "narrative_concentration",
    number: 10,
    label: "Narrative Concentration",
    units: "[0, 1]",
    formula: "top3_phrase_share / total_phrases",
    reliability: "medium",
    predictive_strength: 6,
    timeliness: 5,
    chart: "stat",
    description:
      "Share of discourse held by the top-3 key phrases.",
    interpretation:
      "High values mean a single narrative dominates. Falling concentration with rising buzz = thesis is fragmenting.",
    caveat:
      "Requires LLM-backed phrase classifier. The neutral fallback emits no phrases, so this metric reads zero in that mode.",
    framework: "conviction",
    field: "narrative_concentration",
  },
  {
    id: "institutional_retail_gap",
    number: 11,
    label: "Institutional / Retail Gap",
    units: "Δ pct",
    formula: "institutional_change_pct − retail_sentiment",
    reliability: "experimental",
    predictive_strength: 6,
    timeliness: 4,
    chart: "stat",
    description: "Gap between institutional flow direction and retail sentiment.",
    interpretation:
      "Smart-money divergence: institutions selling while retail stays bullish is a yellow flag. The reverse can be early accumulation.",
    caveat:
      "13F data lags 45 days. Useful as a regime indicator, not a tactical signal.",
    framework: "contrarian",
    field: "institutional_retail_gap",
  },
  {
    id: "event_sensitivity",
    number: 12,
    label: "Event Sensitivity Score",
    units: "stddev",
    formula: "std(daily_returns_30d)",
    reliability: "experimental",
    predictive_strength: 4,
    timeliness: 5,
    chart: "line",
    description:
      "Rolling 30-day standard deviation of daily returns.",
    interpretation:
      "How much a name moves on news. High sensitivity × high buzz = explosive expected move; low sensitivity × high buzz = chatter without conviction.",
    caveat:
      "Cold start when fewer than 30 trading days of price history are available.",
    framework: "trust",
    field: "event_sensitivity",
  },
];

export const RS_METRIC_BY_ID: Record<string, MetricDefinition> =
  Object.fromEntries(RS_METRIC_CATALOG.map((m) => [m.id, m]));

export const FRAMEWORK_QUESTIONS: Record<FrameworkQuestion, string> = {
  mood: "What is the current mood?",
  attention: "How much attention is there?",
  direction: "Is the mood improving or worsening?",
  conviction: "How broad is the conviction?",
  contrarian: "When should I be contrarian?",
  trust: "How much should I trust this signal?",
};
