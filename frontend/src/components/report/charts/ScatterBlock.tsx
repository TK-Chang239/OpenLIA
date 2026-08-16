import { useMemo } from 'react';
import { ChartEmpty } from "./ChartEmpty";
import { paletteColor, niceTicks, formatTick, yScale, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

export interface ScatterSeries { name: string; data: { x: number; y: number }[]; }

interface ScatterSeriesInput {
  name?: string;
  data?: unknown;
  points?: unknown;
}

export interface ScatterBlockProps {
  type: 'scatter_plot';
  title: string;
  // Canonical key is ``points``; ``data`` still accepted for back-compat
  // with reports persisted before the schema normalization.
  series: ScatterSeriesInput[];
  x_label?: string;
  y_label?: string;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

function normalizeScatterSeries(raw: ScatterSeriesInput[] | undefined): ScatterSeries[] {
  return (Array.isArray(raw) ? raw : []).map((s) => {
    const name = typeof s?.name === 'string' ? s.name : '';
    const candidate = Array.isArray(s?.points)
      ? (s.points as unknown[])
      : Array.isArray(s?.data)
        ? (s.data as unknown[])
        : [];
    const data = candidate.flatMap((entry) => {
      if (!entry || typeof entry !== 'object') return [];
      const obj = entry as { x?: unknown; y?: unknown };
      const x = typeof obj.x === 'number' ? obj.x : Number(obj.x);
      const y = typeof obj.y === 'number' ? obj.y : Number(obj.y);
      if (Number.isFinite(x) && Number.isFinite(y)) return [{ x, y }];
      return [];
    });
    return { name, data };
  });
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;
// Inset the data plot area horizontally so dots at xMin/xMax don't render
// directly on the y-axis line (where their left half overlaps with y-tick
// labels) or against the right edge. 10px each side comfortably clears the
// 3.5px dot radius plus the y-tick text gutter.
const X_INSET = 10;

export function ScatterBlock({ title, series: rawSeries, x_label, y_label, options }: ScatterBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;
  const { figureRef, tooltipNode, hover } = useChartTooltip();
  const series = useMemo(() => normalizeScatterSeries(rawSeries), [rawSeries]);

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
        <ChartEmpty />
      </figure>
    );
  }

  const xPlotLeft = L + X_INSET;
  const xPlotRight = W - R - X_INSET;
  const xToPx = (x: number) =>
    chart.xMax === chart.xMin
      ? (xPlotLeft + xPlotRight) / 2
      : xPlotLeft + ((x - chart.xMin) / (chart.xMax - chart.xMin)) * (xPlotRight - xPlotLeft);

  return (
    <figure className="report-chart" ref={figureRef}>
      <figcaption className="report-chart__title">{title}</figcaption>
      <svg
        className="report-line-chart"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ width: '100%', height: 'auto' }}
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
                className="series-dot"
                cx={xToPx(d.x)}
                cy={yScale(d.y, chart.yMin, chart.yMax, T, H - B)}
                r={3.5}
                style={{ fillOpacity: 0.85 }}
                {...hover({
                  label: s.name,
                  rows: [
                    { name: x_label ?? 'x', value: formatTick(d.x) },
                    { name: y_label ?? 'y', value: formatTick(d.y) },
                  ],
                })}
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
      {tooltipNode}
    </figure>
  );
}
