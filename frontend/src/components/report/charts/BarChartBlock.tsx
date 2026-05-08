import { useMemo } from 'react';
import { paletteColor, niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';

export interface BarSeries {
  name: string;
  values: number[];
}

export interface BarChartBlockProps {
  type: 'bar_chart';
  title: string;
  categories: string[];
  series: BarSeries[];
  orientation?: 'vertical' | 'horizontal';
  stacked?: boolean;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;

export function BarChartBlock({
  title,
  categories,
  series: rawSeries,
  orientation = 'vertical',
  stacked = false,
  options,
}: BarChartBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;

  // Defensive normalization: LLM-generated payloads sometimes ship a series
  // entry with missing/null ``values``. Coerce to [] so downstream indexing
  // never throws on ``s.values[ci]``.
  const series = useMemo<BarSeries[]>(
    () =>
      (rawSeries ?? []).map((s) => ({
        name: s?.name ?? '',
        values: Array.isArray(s?.values) ? s.values : [],
      })),
    [rawSeries],
  );

  const safeCategories = useMemo<string[]>(
    () => (Array.isArray(categories) ? categories : []),
    [categories],
  );

  const chart = useMemo(() => {
    if (safeCategories.length === 0 || series.length === 0) return null;
    if (stacked) {
      const stacks = safeCategories.map((_, ci) =>
        series.reduce((acc, s) => acc + (s.values[ci] ?? 0), 0),
      );
      return { mode: 'stacked' as const, maxV: Math.max(0, ...stacks), minV: Math.min(0, ...stacks) };
    }
    const all = series.flatMap((s) => s.values);
    return { mode: 'grouped' as const, maxV: Math.max(0, ...all), minV: Math.min(0, ...all) };
  }, [safeCategories, series, stacked]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  if (orientation === 'horizontal') {
    return (
      <HorizontalBars
        title={title}
        categories={safeCategories}
        series={series}
        showLegend={showLegend}
      />
    );
  }

  const ticks = niceTicks(chart.minV, chart.maxV, 4);
  const yMin = ticks[0] ?? chart.minV;
  const yMax = ticks[ticks.length - 1] ?? chart.maxV;
  const groupW = (W - L - R) / safeCategories.length;
  const innerPad = groupW * 0.18;
  const slotW = groupW - innerPad * 2;
  const barW = chart.mode === 'grouped' ? slotW / Math.max(1, series.length) : slotW;
  const visibleX = visibleXLabels(safeCategories);
  const baseline = yScale(0, yMin, yMax, T, H - B);

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
          ticks.map((t) => {
            const y = yScale(t, yMin, yMax, T, H - B);
            return (
              <g key={`tick-${t}`}>
                <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} />
                <text className="tick-label" x={L - 6} y={y} dy="0.32em" textAnchor="end">
                  {formatTick(t)}
                </text>
              </g>
            );
          })}
        <line className="axis-line" x1={L} x2={W - R} y1={H - B} y2={H - B} />

        {safeCategories.map((_cat, ci) => {
          const slotLeft = L + ci * groupW + innerPad;
          if (chart.mode === 'stacked') {
            let cumPos = 0;
            let cumNeg = 0;
            return (
              <g key={`g-${ci}`}>
                {series.map((s, si) => {
                  const v = s.values[ci] ?? 0;
                  const start = v >= 0 ? cumPos : cumNeg;
                  const end = start + v;
                  const yTop = yScale(Math.max(start, end), yMin, yMax, T, H - B);
                  const yBot = yScale(Math.min(start, end), yMin, yMax, T, H - B);
                  if (v >= 0) cumPos = end;
                  else cumNeg = end;
                  return (
                    <rect
                      key={s.name}
                      x={slotLeft}
                      y={yTop}
                      width={barW}
                      height={Math.max(1, yBot - yTop)}
                      style={{ fill: paletteColor(si) }}
                    />
                  );
                })}
              </g>
            );
          }
          return (
            <g key={`g-${ci}`}>
              {series.map((s, si) => {
                const v = s.values[ci] ?? 0;
                const x = slotLeft + si * barW;
                const yv = yScale(v, yMin, yMax, T, H - B);
                const yTop = Math.min(baseline, yv);
                const h = Math.max(1, Math.abs(baseline - yv));
                return (
                  <rect
                    key={s.name}
                    x={x}
                    y={yTop}
                    width={Math.max(1, barW - 1)}
                    height={h}
                    style={{ fill: paletteColor(si) }}
                  />
                );
              })}
            </g>
          );
        })}
        {safeCategories.map((cat, ci) =>
          visibleX[ci] ? (
            <text
              key={`x-${ci}`}
              className="tick-label"
              x={L + ci * groupW + groupW / 2}
              y={H - B + 14}
              textAnchor="middle"
            >
              {cat}
            </text>
          ) : null,
        )}
      </svg>
      {showLegend && series.length > 1 ? <Legend series={series} /> : null}
    </figure>
  );
}

function HorizontalBars({
  title,
  categories,
  series,
  showLegend,
}: {
  title: string;
  categories: string[];
  series: BarSeries[];
  showLegend: boolean;
}) {
  const all = series.flatMap((s) => s.values);
  const maxV = Math.max(1e-9, ...all);
  const rows = categories.map((c, i) => ({ name: c, value: series[0]?.values[i] ?? 0 }));
  return (
    <figure className="report-chart">
      <figcaption className="report-chart__title">{title}</figcaption>
      <div className="report-bars-h">
        {rows.map((r) => (
          <div className="report-bars-h__row" key={r.name}>
            <div className="report-bars-h__name">{r.name}</div>
            <div className="report-bars-h__track">
              <div className="report-bars-h__fill" style={{ width: `${(r.value / maxV) * 100}%` }} />
            </div>
            <div className="report-bars-h__val">{formatTick(r.value)}</div>
          </div>
        ))}
      </div>
      {showLegend && series.length > 1 ? <Legend series={series} /> : null}
    </figure>
  );
}

function Legend({ series }: { series: BarSeries[] }) {
  return (
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
  );
}
