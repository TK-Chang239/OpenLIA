/**
 * Inline-SVG chart primitives for Retail Sentiment.
 * All charts use design tokens for color and avoid external charting libs
 * to match the dense, mono-numeric aesthetic of the rest of the page.
 */

interface BasePoint {
  x: number | string;
  y: number;
}

interface SparkProps {
  data: BasePoint[];
  height?: number;
  ariaLabel?: string;
  tone?: "accent" | "warn" | "cool" | "error";
}

const SPARK_TONE: Record<NonNullable<SparkProps["tone"]>, { line: string; fill: string }> = {
  accent: { line: "var(--color-feedback-success)", fill: "rgba(168,204,0,0.18)" },
  warn: { line: "var(--color-feedback-warning)", fill: "rgba(220,150,20,0.16)" },
  cool: { line: "var(--color-text-tertiary)", fill: "rgba(176,174,166,0.16)" },
  error: { line: "var(--color-feedback-error)", fill: "rgba(224,92,48,0.16)" },
};

/** Tiny filled spark line. Used in narrative-tracker rows and trending tiles. */
export function Spark({
  data,
  height = 28,
  ariaLabel = "spark",
  tone = "accent",
}: SparkProps) {
  if (data.length === 0) {
    return (
      <div className="text-[10px] text-[--color-text-tertiary]" data-testid="spark-empty">
        No data
      </div>
    );
  }
  const w = 200;
  const ys = data.map((d) => d.y);
  const min = Math.min(...ys);
  const max = Math.max(...ys);
  const range = max - min || 1;
  const norm = (y: number) => height - 2 - ((y - min) / range) * (height - 4);
  const xAt = (i: number) => (i / Math.max(1, data.length - 1)) * w;
  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${norm(d.y)}`)
    .join(" ");
  const fillPath = `${linePath} L ${xAt(data.length - 1)} ${height} L 0 ${height} Z`;
  const palette = SPARK_TONE[tone];

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="rs-spark"
    >
      <path d={fillPath} fill={palette.fill} />
      <path d={linePath} stroke={palette.line} strokeWidth="1.5" fill="none" />
    </svg>
  );
}

interface SentimentLineProps {
  data: BasePoint[];
  height?: number;
  /** Rendered as a faint dashed reference line (e.g. zero or 30d mean). */
  baseline?: number | null;
  ariaLabel?: string;
}

/** Plain sentiment line used for the headline timeline chart. */
export function SentimentLine({
  data,
  height = 140,
  baseline = 0,
  ariaLabel = "sentiment over time",
}: SentimentLineProps) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-[--color-text-tertiary] p-4" data-testid="sentiment-line-empty">
        No history yet.
      </div>
    );
  }
  const w = 600;
  const ys = data.map((d) => d.y);
  const min = Math.min(...ys, baseline ?? Infinity);
  const max = Math.max(...ys, baseline ?? -Infinity);
  const range = max - min || 1;
  const norm = (y: number) => height - 8 - ((y - min) / range) * (height - 16);
  const xAt = (i: number) => 8 + (i / Math.max(1, data.length - 1)) * (w - 16);
  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${norm(d.y)}`)
    .join(" ");

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="sentiment-line"
    >
      {baseline !== null && baseline !== undefined ? (
        <line
          x1={8}
          x2={w - 8}
          y1={norm(baseline)}
          y2={norm(baseline)}
          stroke="var(--color-border-secondary)"
          strokeDasharray="3 4"
        />
      ) : null}
      <path d={linePath} stroke="var(--color-feedback-success)" strokeWidth="2" fill="none" />
      {data.map((d, i) => (
        <circle
          key={i}
          cx={xAt(i)}
          cy={norm(d.y)}
          r={2}
          fill="var(--color-feedback-success)"
        />
      ))}
    </svg>
  );
}

interface BuzzBarsProps {
  data: BasePoint[];
  height?: number;
  ariaLabel?: string;
}

/**
 * Buzz volume bar chart.
 * Color thresholds (per design doc):
 *   ≤1.0× → neutral  / 1.0–1.5× → elevated (warn) / >1.5× → spike (error)
 * A dashed horizontal line marks the 30-day average (y=1.0 in normalized buzz_volume).
 */
export function BuzzBars({
  data,
  height = 120,
  ariaLabel = "buzz volume",
}: BuzzBarsProps) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-[--color-text-tertiary] p-4" data-testid="buzz-bars-empty">
        No buzz history yet.
      </div>
    );
  }
  const w = 600;
  const max = Math.max(...data.map((d) => d.y), 1.6);
  const norm = (y: number) => height - 8 - (y / max) * (height - 16);
  const barW = (w - 16) / data.length - 4;

  const fill = (y: number) => {
    if (y > 1.5) return "var(--color-feedback-error)";
    if (y > 1.0) return "var(--color-feedback-warning)";
    return "var(--color-text-tertiary)";
  };

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="buzz-bars"
    >
      {/* 30d-avg reference line at y=1 */}
      <line
        x1={8}
        x2={w - 8}
        y1={norm(1)}
        y2={norm(1)}
        stroke="var(--color-border-secondary)"
        strokeDasharray="3 4"
      />
      {data.map((d, i) => {
        const x = 8 + i * (barW + 4);
        const y = norm(Math.max(0, d.y));
        const h = height - 8 - y;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(2, barW)}
            height={Math.max(0, h)}
            fill={fill(d.y)}
            rx={1.5}
          />
        );
      })}
    </svg>
  );
}

interface MomentumAreaProps {
  data: BasePoint[];
  height?: number;
  ariaLabel?: string;
}

/** Dual-fill area chart: green above zero, red below zero. */
export function MomentumArea({
  data,
  height = 120,
  ariaLabel = "momentum",
}: MomentumAreaProps) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-[--color-text-tertiary] p-4" data-testid="momentum-area-empty">
        No momentum history yet.
      </div>
    );
  }
  const w = 600;
  const ys = data.map((d) => d.y);
  const absMax = Math.max(0.05, ...ys.map(Math.abs));
  const zero = height / 2;
  const norm = (y: number) => zero - (y / absMax) * (height / 2 - 6);
  const xAt = (i: number) => 8 + (i / Math.max(1, data.length - 1)) * (w - 16);

  const linePath = data
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${norm(d.y)}`)
    .join(" ");

  // Build positive/negative fill polygons by clamping to the zero line.
  const posPath = `M ${xAt(0)} ${zero} ${data
    .map((d, i) => `L ${xAt(i)} ${norm(Math.max(0, d.y))}`)
    .join(" ")} L ${xAt(data.length - 1)} ${zero} Z`;
  const negPath = `M ${xAt(0)} ${zero} ${data
    .map((d, i) => `L ${xAt(i)} ${norm(Math.min(0, d.y))}`)
    .join(" ")} L ${xAt(data.length - 1)} ${zero} Z`;

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="momentum-area"
    >
      <path d={posPath} fill="rgba(168,204,0,0.22)" />
      <path d={negPath} fill="rgba(224,92,48,0.22)" />
      <line
        x1={8}
        x2={w - 8}
        y1={zero}
        y2={zero}
        stroke="var(--color-border-secondary)"
        strokeDasharray="3 4"
      />
      <path
        d={linePath}
        stroke="var(--color-text-primary)"
        strokeWidth="1.5"
        fill="none"
      />
    </svg>
  );
}

interface BullBearStackProps {
  /** Each entry must sum bull + bear ≈ 1 (or any positive total — we normalize). */
  data: Array<{ x: number | string; bull: number; bear: number }>;
  height?: number;
  ariaLabel?: string;
}

/** Stacked-to-100% bull/bear bars per day. */
export function BullBearStack({
  data,
  height = 120,
  ariaLabel = "bull bear ratio",
}: BullBearStackProps) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-[--color-text-tertiary] p-4" data-testid="bull-bear-stack-empty">
        No ratio history yet.
      </div>
    );
  }
  const w = 600;
  const barW = (w - 16) / data.length - 4;

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="bull-bear-stack"
    >
      {data.map((d, i) => {
        const total = d.bull + d.bear || 1;
        const bullFrac = d.bull / total;
        const x = 8 + i * (barW + 4);
        const bullH = (height - 16) * bullFrac;
        const bearH = height - 16 - bullH;
        return (
          <g key={i}>
            <rect
              x={x}
              y={8}
              width={Math.max(2, barW)}
              height={bullH}
              fill="var(--color-feedback-success)"
              rx={1.5}
            />
            <rect
              x={x}
              y={8 + bullH}
              width={Math.max(2, barW)}
              height={bearH}
              fill="var(--color-feedback-error)"
              rx={1.5}
            />
          </g>
        );
      })}
    </svg>
  );
}

interface DivergenceBarsProps {
  data: BasePoint[];
  height?: number;
  ariaLabel?: string;
}

/**
 * Divergence bars colored by significance threshold (per design doc):
 *   > +1.0 → red (panic / contrarian buy)
 *   < -1.0 → green (stealth recovery)
 *   between → gray
 * Bars draw above/below the zero line at the chart's vertical midpoint.
 */
export function DivergenceBars({
  data,
  height = 120,
  ariaLabel = "buzz sentiment divergence",
}: DivergenceBarsProps) {
  if (data.length === 0) {
    return (
      <div className="text-xs text-[--color-text-tertiary] p-4" data-testid="divergence-bars-empty">
        No divergence history yet.
      </div>
    );
  }
  const w = 600;
  const ys = data.map((d) => d.y);
  const absMax = Math.max(2, ...ys.map(Math.abs));
  const zero = height / 2;
  const scale = (height / 2 - 6) / absMax;
  const barW = (w - 16) / data.length - 4;

  const fill = (y: number) => {
    if (y > 1.0) return "var(--color-feedback-error)";
    if (y < -1.0) return "var(--color-feedback-success)";
    return "var(--color-text-tertiary)";
  };

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="divergence-bars"
    >
      <line
        x1={8}
        x2={w - 8}
        y1={zero}
        y2={zero}
        stroke="var(--color-border-secondary)"
      />
      {/* ±1.0 threshold reference */}
      <line
        x1={8}
        x2={w - 8}
        y1={zero - scale * 1}
        y2={zero - scale * 1}
        stroke="var(--color-border-subtle)"
        strokeDasharray="2 4"
      />
      <line
        x1={8}
        x2={w - 8}
        y1={zero + scale * 1}
        y2={zero + scale * 1}
        stroke="var(--color-border-subtle)"
        strokeDasharray="2 4"
      />
      {data.map((d, i) => {
        const x = 8 + i * (barW + 4);
        const h = scale * Math.abs(d.y);
        const y = d.y >= 0 ? zero - h : zero;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={Math.max(2, barW)}
            height={Math.max(1, h)}
            fill={fill(d.y)}
            rx={1.5}
          />
        );
      })}
    </svg>
  );
}

interface SentimentPriceOverlayProps {
  /** Sentiment series, paired by index with `priceCumulativePct` and `buzz`. */
  sentiment: BasePoint[];
  /** Cumulative price % vs window start, same length as `sentiment`. */
  priceCumulativePct: BasePoint[];
  /** Optional buzz × 30d series rendered as faint background bars. */
  buzz?: BasePoint[];
  height?: number;
  ariaLabel?: string;
}

/**
 * Dual-axis overlay for the Overview tab.
 *
 * - Left axis: sentiment score, fixed at [-1, +1] when |y|<=1, else autoscaled.
 * - Right axis: cumulative price % vs window start, autoscaled.
 * - Background: faint buzz bars on a third (hidden) axis.
 *
 * Closes Gap 1: matches the design's "Sentiment vs price (30 days)" panel.
 */
export function SentimentPriceOverlay({
  sentiment,
  priceCumulativePct,
  buzz,
  height = 200,
  ariaLabel = "sentiment vs price",
}: SentimentPriceOverlayProps) {
  if (sentiment.length === 0) {
    return (
      <div
        className="text-xs text-[--color-text-tertiary] p-4"
        data-testid="sentiment-price-overlay-empty"
      >
        No history yet.
      </div>
    );
  }
  const w = 600;
  const padL = 36;
  const padR = 40;
  const padT = 12;
  const padB = 22;
  const innerW = w - padL - padR;
  const innerH = height - padT - padB;

  const sYs = sentiment.map((d) => d.y).filter(Number.isFinite);
  const allSentAbs = Math.max(...sYs.map(Math.abs), 0.5);
  const sMax = allSentAbs <= 1 ? 1 : allSentAbs;
  const sMin = -sMax;
  const sentY = (y: number) =>
    padT + innerH - ((y - sMin) / (sMax - sMin)) * innerH;

  const pYs = priceCumulativePct.map((d) => d.y).filter(Number.isFinite);
  const pMax = pYs.length > 0 ? Math.max(...pYs, 1) : 1;
  const pMin = pYs.length > 0 ? Math.min(...pYs, -1) : -1;
  const priceY = (y: number) =>
    padT + innerH - ((y - pMin) / (pMax - pMin || 1)) * innerH;

  const xN = Math.max(sentiment.length, priceCumulativePct.length, 1);
  const xAt = (i: number) =>
    padL + (i / Math.max(1, xN - 1)) * innerW;

  const sentPath = sentiment
    .filter((d) => Number.isFinite(d.y))
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${sentY(d.y)}`)
    .join(" ");

  const pricePath = priceCumulativePct
    .filter((d) => Number.isFinite(d.y))
    .map((d, i) => `${i === 0 ? "M" : "L"} ${xAt(i)} ${priceY(d.y)}`)
    .join(" ");

  const buzzMax = buzz && buzz.length > 0
    ? Math.max(...buzz.map((b) => (Number.isFinite(b.y) ? b.y : 0)), 1.6)
    : 0;
  const buzzBarW = buzz && buzz.length > 0 ? innerW / buzz.length - 2 : 0;
  const buzzColor = (y: number) => {
    if (y > 1.5) return "rgba(224,92,48,0.22)";
    if (y > 1.0) return "rgba(220,150,20,0.20)";
    return "rgba(176,174,166,0.16)";
  };

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      preserveAspectRatio="none"
      className="block w-full"
      style={{ height }}
      role="img"
      aria-label={ariaLabel}
      data-testid="sentiment-price-overlay"
    >
      {/* Buzz background bars */}
      {buzz && buzz.length > 0
        ? buzz.map((b, i) => {
            if (!Number.isFinite(b.y)) return null;
            const barH = Math.max(0, (b.y / buzzMax) * innerH * 0.9);
            const barX = xAt(i) - buzzBarW / 2;
            const barY = padT + innerH - barH;
            return (
              <rect
                key={i}
                x={barX}
                y={barY}
                width={Math.max(2, buzzBarW)}
                height={barH}
                fill={buzzColor(b.y)}
                rx={1}
              />
            );
          })
        : null}

      {/* Zero line for sentiment */}
      <line
        x1={padL}
        x2={padL + innerW}
        y1={sentY(0)}
        y2={sentY(0)}
        stroke="var(--color-border-secondary)"
        strokeDasharray="3 4"
      />

      {/* Sentiment line + dots */}
      <path
        d={sentPath}
        stroke="var(--color-feedback-success)"
        strokeWidth="2"
        fill="none"
      />
      {sentiment.map((d, i) =>
        Number.isFinite(d.y) ? (
          <circle
            key={`s-${i}`}
            cx={xAt(i)}
            cy={sentY(d.y)}
            r={2}
            fill="var(--color-feedback-success)"
          />
        ) : null,
      )}

      {/* Price line — dashed to match design */}
      {priceCumulativePct.length > 0 ? (
        <path
          d={pricePath}
          stroke="var(--color-text-primary)"
          strokeWidth="1.5"
          strokeDasharray="4 3"
          fill="none"
        />
      ) : null}

      {/* Left axis labels (sentiment) */}
      <g
        fill="var(--color-feedback-success)"
        fontFamily="var(--font-mono, monospace)"
        fontSize="9"
      >
        <text x={padL - 4} y={sentY(sMax) + 3} textAnchor="end">
          {sMax === 1 ? "+1" : sMax.toFixed(1)}
        </text>
        <text x={padL - 4} y={sentY(0) + 3} textAnchor="end">
          0
        </text>
        <text x={padL - 4} y={sentY(sMin) + 3} textAnchor="end">
          {sMin === -1 ? "-1" : sMin.toFixed(1)}
        </text>
      </g>

      {/* Right axis labels (price %) */}
      {priceCumulativePct.length > 0 ? (
        <g
          fill="var(--color-text-primary)"
          fontFamily="var(--font-mono, monospace)"
          fontSize="9"
        >
          <text x={padL + innerW + 4} y={priceY(pMax) + 3}>
            {`${pMax >= 0 ? "+" : ""}${pMax.toFixed(1)}%`}
          </text>
          <text x={padL + innerW + 4} y={priceY(0) + 3}>
            0%
          </text>
          <text x={padL + innerW + 4} y={priceY(pMin) + 3}>
            {`${pMin.toFixed(1)}%`}
          </text>
        </g>
      ) : null}
    </svg>
  );
}

interface ReliabilityScatterProps {
  /** Each metric's predictive_strength (x), timeliness (y), data_volume (size). */
  metrics: Array<{
    id: string;
    label: string;
    predictive_strength: number;
    timeliness: number;
    data_volume: number;
    has_data: boolean;
  }>;
  height?: number;
}

/**
 * Bubble scatter — predictive strength (x) × timeliness (y).
 * Bubble size encodes data_volume. Greyed bubbles for metrics with no data.
 */
export function ReliabilityScatter({
  metrics,
  height = 320,
}: ReliabilityScatterProps) {
  const w = 600;
  const padL = 56;
  const padB = 36;
  const padR = 12;
  const padT = 12;
  const innerW = w - padL - padR;
  const innerH = height - padT - padB;
  const xAt = (v: number) => padL + (v / 10) * innerW;
  const yAt = (v: number) => padT + innerH - (v / 10) * innerH;
  const maxVol = Math.max(1, ...metrics.map((m) => m.data_volume));
  const radiusFor = (v: number) => 6 + Math.sqrt(v / maxVol) * 14;

  return (
    <svg
      viewBox={`0 0 ${w} ${height}`}
      className="block w-full"
      role="img"
      aria-label="reliability scatter"
      data-testid="reliability-scatter"
    >
      {/* axes */}
      <line
        x1={padL}
        y1={padT}
        x2={padL}
        y2={padT + innerH}
        stroke="var(--color-border-subtle)"
      />
      <line
        x1={padL}
        y1={padT + innerH}
        x2={padL + innerW}
        y2={padT + innerH}
        stroke="var(--color-border-subtle)"
      />
      {/* gridlines + tick labels */}
      {[0, 2, 4, 6, 8, 10].map((t) => (
        <g key={`x-${t}`}>
          <line
            x1={xAt(t)}
            y1={padT}
            x2={xAt(t)}
            y2={padT + innerH}
            stroke="var(--color-border-subtle)"
            strokeOpacity="0.4"
          />
          <text
            x={xAt(t)}
            y={padT + innerH + 14}
            textAnchor="middle"
            fontSize="9"
            fontFamily="var(--font-mono, monospace)"
            fill="var(--color-text-tertiary)"
          >
            {t}
          </text>
        </g>
      ))}
      {[0, 2, 4, 6, 8, 10].map((t) => (
        <g key={`y-${t}`}>
          <line
            x1={padL}
            y1={yAt(t)}
            x2={padL + innerW}
            y2={yAt(t)}
            stroke="var(--color-border-subtle)"
            strokeOpacity="0.4"
          />
          <text
            x={padL - 6}
            y={yAt(t) + 3}
            textAnchor="end"
            fontSize="9"
            fontFamily="var(--font-mono, monospace)"
            fill="var(--color-text-tertiary)"
          >
            {t}
          </text>
        </g>
      ))}
      {/* axis titles */}
      <text
        x={padL + innerW / 2}
        y={height - 6}
        textAnchor="middle"
        fontSize="9"
        letterSpacing="0.12em"
        fontFamily="var(--font-mono, monospace)"
        fill="var(--color-text-tertiary)"
      >
        PREDICTIVE STRENGTH →
      </text>
      <text
        x={padL - 40}
        y={padT + innerH / 2}
        textAnchor="middle"
        fontSize="9"
        letterSpacing="0.12em"
        fontFamily="var(--font-mono, monospace)"
        fill="var(--color-text-tertiary)"
        transform={`rotate(-90 ${padL - 40} ${padT + innerH / 2})`}
      >
        TIMELINESS →
      </text>
      {/* bubbles */}
      {metrics.map((m) => (
        <g key={m.id}>
          <circle
            cx={xAt(m.predictive_strength)}
            cy={yAt(m.timeliness)}
            r={radiusFor(m.data_volume)}
            fill={
              m.has_data
                ? "var(--color-accent-primary)"
                : "var(--color-text-tertiary)"
            }
            opacity={m.has_data ? 0.55 : 0.25}
          />
          <circle
            cx={xAt(m.predictive_strength)}
            cy={yAt(m.timeliness)}
            r={radiusFor(m.data_volume)}
            fill="none"
            stroke={
              m.has_data
                ? "var(--color-accent-primary)"
                : "var(--color-text-tertiary)"
            }
            strokeWidth="1"
          />
          <text
            x={xAt(m.predictive_strength)}
            y={yAt(m.timeliness) - radiusFor(m.data_volume) - 4}
            textAnchor="middle"
            fontSize="9"
            fontFamily="var(--font-mono, monospace)"
            fill="var(--color-text-secondary)"
          >
            {m.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
