import { useMemo } from 'react';
import { paletteColor, niceTicks, formatTick, yScale, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';

export interface ScatterSeries { name: string; data: { x: number; y: number }[]; }

export interface ScatterBlockProps {
  type: 'scatter_plot';
  title: string;
  series: ScatterSeries[];
  x_label?: string;
  y_label?: string;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;

export function ScatterBlock({ title, series, x_label, y_label, options }: ScatterBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;

  const chart = useMemo(() => {
    const xs = series.flatMap((s) => s.data.map((d) => d.x));
    const ys = series.flatMap((s) => s.data.map((d) => d.y));
    if (xs.length === 0) return null;
    const xTicks = niceTicks(Math.min(...xs), Math.max(...xs), 5);
    const yTicks = niceTicks(Math.min(...ys), Math.max(...ys), 4);
    return {
      xTicks,
      yTicks,
      xMin: xTicks[0]!,
      xMax: xTicks[xTicks.length - 1]!,
      yMin: yTicks[0]!,
      yMax: yTicks[yTicks.length - 1]!,
    };
  }, [series]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  const xToPx = (x: number) =>
    chart.xMax === chart.xMin
      ? (L + W - R) / 2
      : L + ((x - chart.xMin) / (chart.xMax - chart.xMin)) * (W - L - R);

  return (
    <figure className="report-chart">
      <figcaption className="report-chart__title">{title}</figcaption>
      <svg
        className="report-line-chart"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={title}
      >
        {showGrid &&
          chart.yTicks.map((t) => {
            const y = yScale(t, chart.yMin, chart.yMax, T, H - B);
            return (
              <g key={`y-${t}`}>
                <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} />
                <text className="tick-label" x={L - 6} y={y} dy="0.32em" textAnchor="end">
                  {formatTick(t)}
                </text>
              </g>
            );
          })}
        <line className="axis-line" x1={L} x2={W - R} y1={H - B} y2={H - B} />
        <line className="axis-line" x1={L} x2={L} y1={T} y2={H - B} />

        {chart.xTicks.map((t) => (
          <text key={`x-${t}`} className="tick-label" x={xToPx(t)} y={H - B + 14} textAnchor="middle">
            {formatTick(t)}
          </text>
        ))}

        {series.map((s, si) => (
          <g key={s.name} style={{ fill: paletteColor(si) }}>
            {s.data.map((d, i) => (
              <circle
                key={i}
                cx={xToPx(d.x)}
                cy={yScale(d.y, chart.yMin, chart.yMax, T, H - B)}
                r={3.5}
                style={{ fillOpacity: 0.85 }}
              />
            ))}
          </g>
        ))}

        {x_label ? (
          <text className="tick-label" x={(L + W - R) / 2} y={H - 4} textAnchor="middle">
            {x_label}
          </text>
        ) : null}
        {y_label ? (
          <text className="tick-label" x={6} y={T + 4} textAnchor="start">
            {y_label}
          </text>
        ) : null}
      </svg>
      {showLegend && series.length > 1 ? (
        <div className="report-chart__legend">
          {series.map((s, si) => (
            <span key={s.name}>
              <span
                className="report-chart__legend-swatch"
                style={{ background: paletteColor(si) }}
              />
              {s.name}
            </span>
          ))}
        </div>
      ) : null}
    </figure>
  );
}
