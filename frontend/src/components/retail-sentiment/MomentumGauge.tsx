import { useTranslation } from "react-i18next";

interface Props {
  /** Sentiment momentum (Δ score). Expected range -0.3..+0.3 but auto-clamped. */
  momentum: number | null | undefined;
  /** Range half-width — the gauge maps [-range, +range] onto the 180 deg arc. */
  range?: number;
  size?: number;
}

/**
 * Smaller mirror of SentimentGauge for sentiment momentum.
 * Two-zone color: red (deteriorating) and green (improving).
 */
export function MomentumGauge({
  momentum,
  range = 0.3,
  size = 240,
}: Props) {
  const { t } = useTranslation();
  const has = momentum !== null && momentum !== undefined && Number.isFinite(momentum);
  const raw = has ? Math.max(-range, Math.min(range, Number(momentum))) : 0;
  const percent = ((raw + range) / (2 * range)) * 100;
  const cx = 160;
  const cy = 160;
  const radius = 120;
  const angleDeg = 180 - (percent / 100) * 180;
  const angleRad = (angleDeg * Math.PI) / 180;
  const tipX = cx + (radius - 12) * Math.cos(angleRad);
  const tipY = cy - (radius - 12) * Math.sin(angleRad);

  const tone = !has
    ? "var(--color-text-tertiary)"
    : raw > 0
      ? "var(--color-feedback-success)"
      : raw < 0
        ? "var(--color-feedback-error)"
        : "var(--color-text-secondary)";

  const display = has
    ? `${raw > 0 ? "+" : ""}${raw.toFixed(3)}`
    : "—";
  const dir = !has
    ? "—"
    : raw > 0
      ? t("retail_sentiment.momentum_gauge.improving")
      : raw < 0
        ? t("retail_sentiment.momentum_gauge.deteriorating")
        : t("retail_sentiment.momentum_gauge.flat");

  return (
    <div
      className="relative w-full"
      style={{ maxWidth: size }}
      role="img"
      aria-label={t("retail_sentiment.momentum_gauge.aria", { value: display, dir })}
      data-testid="momentum-gauge"
    >
      <svg
        viewBox="0 0 320 180"
        preserveAspectRatio="xMidYMid meet"
        className="block w-full h-auto"
      >
        <g strokeWidth="20" fill="none" strokeLinecap="butt">
          <path
            d="M 40 160 A 120 120 0 0 1 160 40"
            stroke="var(--color-feedback-error)"
            opacity={0.55}
          />
          <path
            d="M 160 40 A 120 120 0 0 1 280 160"
            stroke="var(--color-feedback-success)"
            opacity={0.55}
          />
        </g>
        <g
          fill="var(--color-text-tertiary)"
          fontFamily="var(--font-mono, monospace)"
          fontSize="9"
          letterSpacing="0.5"
        >
          <text x="40" y="178" textAnchor="middle">
            -{range}
          </text>
          <text x="160" y="28" textAnchor="middle">0</text>
          <text x="280" y="178" textAnchor="middle">
            +{range}
          </text>
        </g>
        {has ? (
          <g>
            <line
              x1={cx}
              y1={cy}
              x2={tipX}
              y2={tipY}
              stroke={tone}
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <circle cx={cx} cy={cy} r="7" fill="var(--color-text-primary)" />
            <circle cx={cx} cy={cy} r="3" fill={tone} />
          </g>
        ) : null}
      </svg>
      <div className="absolute left-0 right-0 bottom-2 text-center">
        <span
          className="font-mono font-medium tabular-nums"
          style={{
            fontSize: "32px",
            lineHeight: 1,
            color: tone,
          }}
        >
          {display}
        </span>
        <div
          className="font-mono mt-1"
          style={{
            fontSize: "10px",
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--color-text-tertiary)",
          }}
        >
          {dir}
        </div>
      </div>
    </div>
  );
}
