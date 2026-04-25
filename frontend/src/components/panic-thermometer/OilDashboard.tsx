import type { PanelResult } from "../../api/panic-thermometer";

interface Props {
  result: PanelResult | undefined;
}

interface CachedSeries {
  price?: number[];
  high?: number[];
  low?: number[];
}

function getSeries(result: PanelResult | undefined): number[] {
  if (!result) return [];
  const cached = (result.extras as { raw_series?: CachedSeries } | undefined)
    ?.raw_series;
  if (cached?.price && Array.isArray(cached.price)) return cached.price;
  // Fallback: derive from resolved value (single point) so the dashboard renders
  // even when raw_series is not echoed by the backend.
  const price =
    typeof result.resolved_values?.price === "number"
      ? (result.resolved_values.price as number)
      : null;
  return price === null ? [] : [price];
}

function buildPath(series: number[], width: number, height: number): string {
  if (series.length === 0) return "";
  const min = Math.min(...series);
  const max = Math.max(...series);
  const span = max - min || 1;
  const stepX = series.length === 1 ? 0 : width / (series.length - 1);
  return series
    .map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

export function OilDashboard({ result }: Props): JSX.Element {
  const series = getSeries(result);
  const threshold = Number(result?.resolved_values?.price_threshold ?? 85);
  const width = 600;
  const height = 200;
  const min = series.length ? Math.min(...series, threshold) : threshold;
  const max = series.length ? Math.max(...series, threshold) : threshold;
  const span = max - min || 1;
  const yThreshold = height - ((threshold - min) / span) * height;

  return (
    <div data-testid="oil-dashboard">
      <h4>Oil Price Duration</h4>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Oil price line chart"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        <line
          x1={0}
          y1={yThreshold}
          x2={width}
          y2={yThreshold}
          stroke="var(--color-feedback-warning)"
          strokeDasharray="4 4"
        />
        {series.length > 0 ? (
          <path
            d={buildPath(series, width, height)}
            fill="none"
            stroke="var(--color-text-primary)"
            strokeWidth={1.5}
          />
        ) : (
          <text x={width / 2} y={height / 2} textAnchor="middle">
            No price data
          </text>
        )}
      </svg>
      <p>
        Threshold: ${threshold.toFixed(2)} — Latest: $
        {series.length ? series[series.length - 1].toFixed(2) : "n/a"}
      </p>
    </div>
  );
}
