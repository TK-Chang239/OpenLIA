interface Props {
  score: number;
  size?: number;
}

/**
 * Inline-SVG semicircular gauge for sentiment score in [-1, 1].
 * Bullish → green sweep; bearish → red sweep; neutral → grey.
 */
export function SentimentGauge({ score, size = 160 }: Props) {
  const clamped = Math.max(-1, Math.min(1, score));
  const angle = (clamped + 1) * 90; // map [-1,1] → [0,180]
  const radius = size / 2 - 12;
  const cx = size / 2;
  const cy = size / 2;
  const startX = cx - radius;
  const startY = cy;
  const endX = cx + radius * Math.cos(Math.PI - (angle * Math.PI) / 180);
  const endY = cy - radius * Math.sin(Math.PI - (angle * Math.PI) / 180);
  const largeArc = angle > 180 ? 1 : 0;
  const tone =
    clamped > 0.2
      ? "var(--color-feedback-success)"
      : clamped < -0.2
        ? "var(--color-feedback-error)"
        : "var(--color-text-secondary)";

  return (
    <svg
      width={size}
      height={size / 2 + 8}
      viewBox={`0 0 ${size} ${size / 2 + 8}`}
      role="img"
      aria-label={`Sentiment gauge ${clamped.toFixed(2)}`}
    >
      <path
        d={`M ${startX} ${startY} A ${radius} ${radius} 0 0 1 ${cx + radius} ${cy}`}
        stroke="var(--color-border-subtle)"
        strokeWidth="8"
        fill="none"
      />
      <path
        d={`M ${startX} ${startY} A ${radius} ${radius} 0 ${largeArc} 1 ${endX} ${endY}`}
        stroke={tone}
        strokeWidth="8"
        fill="none"
        strokeLinecap="round"
      />
      <text
        x={cx}
        y={cy - 4}
        textAnchor="middle"
        fill="var(--color-text-primary)"
        fontSize="20"
        fontWeight="600"
      >
        {clamped.toFixed(2)}
      </text>
    </svg>
  );
}
