import { useMemo } from 'react';
import { paletteColor, niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';

export interface ComboSeries { name: string; values: number[]; }

export interface ComboChartBlockProps {
  type: 'combo_chart';
  title: string;
  categories: string[];
  bar_series: ComboSeries[];
  line_series: ComboSeries[];
  y_left_label?: string;
  y_right_label?: string;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

const { W, H } = CHART_VIEWBOX;
const { L, T, B } = CHART_PADDING;
const R = 44;

export function ComboChartBlock({
  title,
  categories,
  bar_series,
  line_series,
  y_left_label,
  y_right_label,
  options,
}: ComboChartBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;

  const chart = useMemo(() => {
    if (categories.length === 0) return null;
    const barAll = bar_series.flatMap((s) => s.values).concat([0]);
    const lineAll = line_series.flatMap((s) => s.values).concat([0]);
    const lTicks = niceTicks(Math.min(...barAll), Math.max(...barAll), 4);
    const rTicks = lineAll.length > 1 ? niceTicks(Math.min(...lineAll), Math.max(...lineAll), 4) : lTicks;
    return {
      lTicks,
      rTicks,
      lMin: lTicks[0]!,
      lMax: lTicks[lTicks.length - 1]!,
      rMin: rTicks[0]!,
      rMax: rTicks[rTicks.length - 1]!,
    };
  }, [categories, bar_series, line_series]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  const slot = (W - L - R) / categories.length;
  const innerPad = slot * 0.18;
  const slotW = slot - innerPad * 2;
  const barW = slotW / Math.max(1, bar_series.length);
  const visibleX = visibleXLabels(categories);
  const baselineL = yScale(Math.max(chart.lMin, 0), chart.lMin, chart.lMax, T, H - B);

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
          chart.lTicks.map((t) => {
            const y = yScale(t, chart.lMin, chart.lMax, T, H - B);
            return (
              <g key={`l-${t}`}>
                <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} />
                <text className="tick-label" x={L - 6} y={y} dy="0.32em" textAnchor="end">
                  {formatTick(t)}
                </text>
              </g>
            );
          })}
        <line className="axis-line" x1={L} x2={W - R} y1={H - B} y2={H - B} />
        <line className="axis-line" x1={L} x2={L} y1={T} y2={H - B} />
        <line className="axis-line" x1={W - R} x2={W - R} y1={T} y2={H - B} />
        {chart.rTicks.map((t) => (
          <text key={`r-${t}`} className="tick-label" x={W - R + 6} y={yScale(t, chart.rMin, chart.rMax, T, H - B)} dy="0.32em" textAnchor="start">
            {formatTick(t)}
          </text>
        ))}
        {y_left_label ? (
          <text className="tick-label" x={6} y={T - 4} textAnchor="start">{y_left_label}</text>
        ) : null}
        {y_right_label ? (
          <text className="tick-label" x={W - 6} y={T - 4} textAnchor="end">{y_right_label}</text>
        ) : null}

        {categories.map((_cat, ci) => (
          <g key={`bars-${ci}`}>
            {bar_series.map((s, si) => {
              const v = s.values[ci] ?? 0;
              const x = L + ci * slot + innerPad + si * barW;
              const yv = yScale(v, chart.lMin, chart.lMax, T, H - B);
              return (
                <rect
                  key={s.name}
                  x={x}
                  y={Math.min(baselineL, yv)}
                  width={Math.max(1, barW - 1)}
                  height={Math.max(1, Math.abs(baselineL - yv))}
                  style={{ fill: paletteColor(si) }}
                />
              );
            })}
          </g>
        ))}

        {line_series.map((s, si) => {
          const points = s.values.map((v, i) => `${L + i * slot + slot / 2},${yScale(v, chart.rMin, chart.rMax, T, H - B)}`).join(' ');
          const color = paletteColor(bar_series.length + si);
          return (
            <g key={s.name}>
              <polyline className="series-line" points={points} style={{ stroke: color }} />
              {s.values.map((v, i) => (
                <circle
                  key={i}
                  className="series-dot"
                  cx={L + i * slot + slot / 2}
                  cy={yScale(v, chart.rMin, chart.rMax, T, H - B)}
                  r={2.5}
                  style={{ fill: color }}
                />
              ))}
            </g>
          );
        })}

        {categories.map((cat, ci) =>
          visibleX[ci] ? (
            <text key={`x-${ci}`} className="tick-label" x={L + ci * slot + slot / 2} y={H - B + 14} textAnchor="middle">
              {cat}
            </text>
          ) : null,
        )}
      </svg>
      {showLegend ? (
        <div className="report-chart__legend">
          {[...bar_series, ...line_series].map((s, si) => (
            <span key={s.name}>
              <span className="report-chart__legend-swatch" style={{ background: paletteColor(si) }} />
              {s.name}
            </span>
          ))}
        </div>
      ) : null}
    </figure>
  );
}
