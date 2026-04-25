import type { PanelResult } from "../../api/panic-thermometer";

interface Props {
  result: PanelResult | undefined;
}

const STATUS_FOR_VALUE = (v: number, amber: number, red: number): string => {
  if (v > red) return "var(--color-feedback-error)";
  if (v > amber) return "var(--color-feedback-warning)";
  return "var(--color-feedback-success)";
};

export function WageGrowthDashboard({ result }: Props): JSX.Element {
  const cached = (result?.extras as { raw_series?: { value?: number[] } } | undefined)
    ?.raw_series?.value;
  const values: number[] = Array.isArray(cached) ? cached : [];
  const amber = Number(result?.resolved_values?.wage_threshold_amber ?? 0.4);
  const red = Number(result?.resolved_values?.wage_threshold_red ?? 0.5);
  const width = 600;
  const height = 180;
  const max = Math.max(...values, red, 1);
  const barW = values.length ? width / values.length : 0;

  return (
    <div data-testid="wage-growth-dashboard">
      <h4>Wage Growth (Average Hourly Earnings MoM)</h4>
      <svg
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Wage growth bar chart"
        style={{ width: "100%", height: "auto", display: "block" }}
      >
        {values.length === 0 ? (
          <text x={width / 2} y={height / 2} textAnchor="middle">
            No wage data
          </text>
        ) : (
          values.map((v, i) => {
            const h = (Math.abs(v) / max) * height;
            return (
              <rect
                key={i}
                x={i * barW + 1}
                y={height - h}
                width={Math.max(1, barW - 2)}
                height={h}
                fill={STATUS_FOR_VALUE(v, amber, red)}
              />
            );
          })
        )}
      </svg>
      <p>
        Latest: {values.length ? values[values.length - 1].toFixed(2) : "n/a"}%
        — amber {amber}%, red {red}%
      </p>
    </div>
  );
}
