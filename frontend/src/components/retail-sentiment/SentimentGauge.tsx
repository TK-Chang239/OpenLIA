import { useTranslation } from "react-i18next";

interface Props {
  /** Sentiment score. Auto-detects scale: |x|<=1 → [-1,+1]; else clamped 0..100. */
  score: number | null | undefined;
  /** Optional 24h delta (in same scale units as `score`) for the headline display. */
  delta24h?: number | null;
  /** Optional 7d delta. */
  delta7d?: number | null;
  /** Override scale detection. */
  scale?: "signed" | "percent";
  size?: number;
}

interface Zone {
  start: number;
  end: number;
  color: string;
  label: string;
}

/**
 * 0-100 normalized zones. Score is rescaled to this band before lookup.
 * Colors come from semantic feedback tokens with raw fallbacks for the
 * intermediate bands not represented by semantic tokens.
 */
const ZONES: Zone[] = [
  { start: 0, end: 20, color: "var(--color-feedback-error)", label: "capitulation" },
  { start: 20, end: 40, color: "var(--color-feedback-error)", label: "fearful" },
  { start: 40, end: 60, color: "var(--color-text-tertiary)", label: "calm" },
  { start: 60, end: 80, color: "var(--color-feedback-success)", label: "greedy" },
  { start: 80, end: 100, color: "var(--color-accent-primary)", label: "frothy" },
];

function detectScale(value: number, override?: "signed" | "percent"): "signed" | "percent" {
  if (override) return override;
  return Math.abs(value) <= 1 ? "signed" : "percent";
}

function toPercent(value: number, scale: "signed" | "percent"): number {
  if (scale === "signed") return Math.max(0, Math.min(100, ((value + 1) / 2) * 100));
  return Math.max(0, Math.min(100, value));
}

function regimeFor(percent: number): Zone {
  return ZONES.find((z) => percent >= z.start && percent < z.end) ?? ZONES[ZONES.length - 1];
}

export function SentimentGauge({
  score,
  delta24h,
  delta7d,
  scale,
  size = 320,
}: Props) {
  const { t } = useTranslation();
  const hasScore = score !== null && score !== undefined && Number.isFinite(score);
  const rawIn = hasScore ? Number(score) : 0;
  const detected = detectScale(rawIn, scale);
  // Clamp to the scale's natural range so displayed value matches the gauge.
  const raw =
    detected === "signed"
      ? Math.max(-1, Math.min(1, rawIn))
      : Math.max(0, Math.min(100, rawIn));
  const percent = hasScore ? toPercent(raw, detected) : 50;
  const zone = regimeFor(percent);

  const cx = 160;
  const cy = 160;
  const radius = 120;
  const angleDeg = 180 - (percent / 100) * 180;
  const angleRad = (angleDeg * Math.PI) / 180;
  const tipX = cx + (radius - 12) * Math.cos(angleRad);
  const tipY = cy - (radius - 12) * Math.sin(angleRad);

  const displayValue = hasScore
    ? detected === "signed"
      ? raw.toFixed(2)
      : Math.round(raw).toString()
    : "—";
  const denom = detected === "signed" ? "/+1" : "/100";

  const fmtDelta = (v: number | null | undefined): string => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "—";
    const sign = v > 0 ? "+" : "";
    return detected === "signed" ? `${sign}${v.toFixed(2)}` : `${sign}${Math.round(v)}`;
  };

  const sentimentClass = (v: number | null | undefined): string => {
    if (v === null || v === undefined || !Number.isFinite(v)) return "text-[--color-text-tertiary]";
    if (v > 0) return "text-[--color-feedback-success]";
    if (v < 0) return "text-[--color-feedback-error]";
    return "text-[--color-text-secondary]";
  };

  const arcs = [
    { d: "M 40 160 A 120 120 0 0 1 76.85 73.15", color: ZONES[0].color },
    { d: "M 76.85 73.15 A 120 120 0 0 1 160 40", color: ZONES[1].color },
    { d: "M 160 40 A 120 120 0 0 1 243.15 73.15", color: ZONES[2].color },
    { d: "M 243.15 73.15 A 120 120 0 0 1 280 160", color: ZONES[3].color },
    { d: "M 280 160 A 120 120 0 0 1 280 160", color: ZONES[4].color },
  ];

  return (
    <div
      className="relative w-full"
      style={{ maxWidth: size }}
      role="img"
      aria-label={t("retail_sentiment.sentiment_gauge.aria", {
        value: displayValue,
        label: t(`retail_sentiment.sentiment_gauge.${zone.label}`),
      })}
      data-testid="sentiment-gauge"
    >
      <svg
        viewBox="0 0 320 180"
        preserveAspectRatio="xMidYMid meet"
        className="block w-full h-auto"
      >
        <g strokeWidth="22" fill="none" strokeLinecap="butt">
          {arcs.map((a, i) => (
            <path key={i} d={a.d} stroke={a.color} opacity={0.7} />
          ))}
          {/* Frothy zone redrawn (matches design's last-segment overlap) */}
          <path
            d="M 243.15 73.15 A 120 120 0 0 1 280 160"
            stroke={ZONES[4].color}
            opacity={0.95}
          />
        </g>

        {/* tick labels */}
        <g
          fill="var(--color-text-tertiary)"
          fontFamily="var(--font-mono, monospace)"
          fontSize="9"
          letterSpacing="0.5"
        >
          <text x="40" y="178" textAnchor="middle">
            {detected === "signed" ? "-1" : "0"}
          </text>
          <text x="76" y="60" textAnchor="middle">
            {detected === "signed" ? "-0.6" : "20"}
          </text>
          <text x="160" y="28" textAnchor="middle">
            {detected === "signed" ? "0" : "50"}
          </text>
          <text x="244" y="60" textAnchor="middle">
            {detected === "signed" ? "+0.6" : "80"}
          </text>
          <text x="280" y="178" textAnchor="middle">
            {detected === "signed" ? "+1" : "100"}
          </text>
        </g>

        {/* needle */}
        {hasScore ? (
          <g>
            <line
              x1={cx}
              y1={cy}
              x2={tipX}
              y2={tipY}
              stroke="var(--color-text-primary)"
              strokeWidth="2.5"
              strokeLinecap="round"
            />
            <circle cx={cx} cy={cy} r="7" fill="var(--color-text-primary)" />
            <circle cx={cx} cy={cy} r="3" fill="var(--color-accent-primary)" />
          </g>
        ) : null}

        {/* zone labels */}
        <g
          fill="var(--color-text-tertiary)"
          fontFamily="var(--font-mono, monospace)"
          fontSize="8"
          letterSpacing="1"
          textAnchor="middle"
        >
          <text x="58" y="120" transform="rotate(-72 58 120)">
            {t("retail_sentiment.sentiment_gauge.fear")}
          </text>
          <text x="105" y="55" transform="rotate(-36 105 55)">
            {t("retail_sentiment.sentiment_gauge.cautious")}
          </text>
          <text x="160" y="58">{t("retail_sentiment.sentiment_gauge.calm_caps")}</text>
          <text x="215" y="55" transform="rotate(36 215 55)">
            {t("retail_sentiment.sentiment_gauge.greedy_caps")}
          </text>
          <text x="262" y="120" transform="rotate(72 262 120)">
            {t("retail_sentiment.sentiment_gauge.frothy_caps")}
          </text>
        </g>
      </svg>

      <div className="absolute left-0 right-0 bottom-2 text-center">
        <span
          className="font-mono font-medium text-[--color-text-primary] tabular-nums"
          style={{ fontSize: "44px", lineHeight: 1, letterSpacing: "-0.01em" }}
        >
          {displayValue}
        </span>
        <span className="font-mono text-[13px] text-[--color-text-tertiary] ml-1">
          {denom}
        </span>
        <div
          className="font-mono mt-1.5"
          style={{
            fontSize: "10.5px",
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: zone.color,
          }}
        >
          {hasScore
            ? t(`retail_sentiment.sentiment_gauge.${zone.label}`)
            : t("retail_sentiment.sentiment_gauge.awaiting")}
        </div>
      </div>

      <div
        className="grid grid-cols-2 gap-3 px-2 pt-3 mt-2 border-t"
        style={{ borderColor: "var(--color-border-subtle)" }}
      >
        <div className="flex flex-col gap-0.5">
          <span className="rs-mono-label">
            {t("retail_sentiment.sentiment_gauge.delta_24h")}
          </span>
          <span className={`rs-mono-value ${sentimentClass(delta24h)}`}>
            {fmtDelta(delta24h)}
          </span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="rs-mono-label">
            {t("retail_sentiment.sentiment_gauge.delta_7d")}
          </span>
          <span className={`rs-mono-value ${sentimentClass(delta7d)}`}>
            {fmtDelta(delta7d)}
          </span>
        </div>
      </div>
    </div>
  );
}
