import { useTranslation } from "react-i18next";

interface Point {
  x: number | string;
  y: number;
}

interface Props {
  data: Point[];
  height?: number;
  baseline?: number | null;
  ariaLabel?: string;
}

/**
 * Minimal inline-SVG line chart. Recharts is overkill for the small
 * 7-day trend strips on the Overview tab.
 */
export function TrendChart({
  data,
  height = 80,
  baseline,
  ariaLabel,
}: Props) {
  const { t } = useTranslation();
  const label = ariaLabel ?? t("retail_sentiment.trend_chart.aria");
  if (data.length === 0) {
    return (
      <div
        className="text-xs text-[--color-text-secondary]"
        data-testid="trend-empty"
      >
        {t("retail_sentiment.trend_chart.empty")}
      </div>
    );
  }
  const width = Math.max(120, data.length * 20);
  const ys = data.map((d) => d.y);
  const min = Math.min(...ys, baseline ?? Infinity);
  const max = Math.max(...ys, baseline ?? -Infinity);
  const range = max - min || 1;
  const norm = (y: number): number =>
    height - 4 - ((y - min) / range) * (height - 8);

  const path = data
    .map(
      (d, i) =>
        `${i === 0 ? "M" : "L"} ${(i / Math.max(1, data.length - 1)) * (width - 4) + 2} ${norm(d.y)}`,
    )
    .join(" ");

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={label}
      data-testid="trend-chart"
    >
      {baseline !== null && baseline !== undefined ? (
        <line
          x1={2}
          x2={width - 2}
          y1={norm(baseline)}
          y2={norm(baseline)}
          stroke="var(--color-border-secondary)"
          strokeDasharray="3 3"
        />
      ) : null}
      <path
        d={path}
        stroke="var(--color-accent-primary)"
        strokeWidth="2"
        fill="none"
      />
    </svg>
  );
}
