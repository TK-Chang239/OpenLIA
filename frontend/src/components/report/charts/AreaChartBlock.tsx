import { useMemo } from 'react';
import { paletteColor, niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

export interface AreaSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

interface AreaSeriesInput {
  name?: string;
  data?: unknown;
  values?: unknown;
}

export interface AreaChartBlockProps {
  type: 'area_chart';
  title: string;
  // Canonical: ``categories`` + ``series[].values``; legacy ``data: [{x,y}]``
  // still accepted on read for back-compat with persisted reports.
  series: AreaSeriesInput[];
  categories?: string[];
  stacked?: boolean;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

function normalizeAreaSeries(
  rawSeries: AreaSeriesInput[] | undefined,
  rawCategories: string[] | undefined,
): { series: AreaSeries[]; xs: string[] } {
  const list = Array.isArray(rawSeries) ? rawSeries : [];
  const declared = Array.isArray(rawCategories) ? rawCategories.map(String) : [];
  let derived: string[] = [];
  if (declared.length === 0) {
    const firstData = list[0]?.data;
    if (Array.isArray(firstData) && firstData.every((d) => d && typeof d === 'object' && 'x' in d)) {
      derived = (firstData as { x: unknown }[]).map((d) => String(d.x));
    }
  }
  const xs = declared.length > 0 ? declared : derived;
  const series = list.map((s) => {
    const name = typeof s?.name === 'string' ? s.name : '';
    const candidate = Array.isArray(s?.values)
      ? (s.values as unknown[])
      : Array.isArray(s?.data)
        ? (s.data as unknown[])
        : [];
    const dataPoints = candidate.map((entry, i): { x: string | number; y: number } => {
      if (entry && typeof entry === 'object' && 'y' in (entry as object)) {
        const obj = entry as { x?: unknown; y?: unknown };
        return {
          x: typeof obj.x === 'number' || typeof obj.x === 'string' ? obj.x : xs[i] ?? i,
          y: typeof obj.y === 'number' ? obj.y : 0,
        };
      }
      return { x: xs[i] ?? i, y: typeof entry === 'number' ? entry : 0 };
    });
    return { name, data: dataPoints };
  });
  return { series, xs };
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;

export function AreaChartBlock({
  title,
  series: rawSeries,
  categories: rawCategories,
  stacked = false,
  options,
}: AreaChartBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;
  const { figureRef, tooltipNode, hover } = useChartTooltip();
  const { series, xs } = useMemo(
    () => normalizeAreaSeries(rawSeries, rawCategories),
    [rawSeries, rawCategories],
  );

  const chart = useMemo(() => {
    const cats = xs.length > 0 ? xs : series[0]?.data.map((d) => String(d.x)) ?? [];
    if (cats.length === 0) return null;
    const stacked_cum: number[][] = [];
    let running = new Array(cats.length).fill(0);
    if (stacked) {
      for (const s of series) {
        const next = s.data.map((d, i) => running[i] + d.y);
        stacked_cum.push(next);
        running = next;
      }
    } else {
      for (const s of series) stacked_cum.push(s.data.map((d) => d.y));
    }
    const allY = stacked ? stacked_cum.flat().concat([0]) : series.flatMap((s) => s.data.map((d) => d.y)).concat([0]);
    const ticks = niceTicks(Math.min(...allY), Math.max(...allY), 4);
    const yMin = ticks[0]!;
    const yMax = ticks[ticks.length - 1]!;
    const xStep = cats.length > 1 ? (W - L - R) / (cats.length - 1) : 0;
    return { cats, ticks, yMin, yMax, xStep, stacked_cum };
  }, [series, stacked, xs]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  const visibleX = visibleXLabels(chart.cats);
  const baseline = yScale(chart.yMin, chart.yMin, chart.yMax, T, H - B);

  return (
    <figure className="report-chart" ref={figureRef}>
      <figcaption className="report-chart__title">{title}</figcaption>
      <svg
        className="report-line-chart"
        viewBox={`0 0 ${W} ${H}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={title}
      >
        {showGrid &&
          chart.ticks.map((t) => {
            const y = yScale(t, chart.yMin, chart.yMax, T, H - B);
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

        {chart.stacked_cum.map((vals, si) => {
          const points = vals.map((v, i) => `${L + i * chart.xStep},${yScale(v, chart.yMin, chart.yMax, T, H - B)}`);
          const lower = stacked && si > 0
            ? chart.stacked_cum[si - 1]!.map((v, i) => `${L + i * chart.xStep},${yScale(v, chart.yMin, chart.yMax, T, H - B)}`)
            : null;
          const close = lower
            ? lower.slice().reverse().join(' ')
            : `${L + (vals.length - 1) * chart.xStep},${baseline} ${L},${baseline}`;
          const polyPath = `${points.join(' ')} ${close}`;
          return (
            <g key={si}>
              <polygon
                points={polyPath}
                style={{ fill: paletteColor(si), fillOpacity: 0.18, stroke: 'none' }}
              />
              <polyline
                className="series-line"
                points={points.join(' ')}
                style={{ stroke: paletteColor(si) }}
              />
            </g>
          );
        })}

        {chart.cats.map((cat, ci) =>
          visibleX[ci] ? (
            <text
              key={`x-${ci}`}
              className="tick-label"
              x={L + ci * chart.xStep}
              y={H - B + 14}
              textAnchor="middle"
            >
              {cat}
            </text>
          ) : null,
        )}
        {chart.cats.map((cat, ci) => {
          const cx = L + ci * chart.xStep;
          const halfStep = chart.xStep > 0 ? chart.xStep / 2 : (W - L - R) / 2;
          const x = Math.max(L, cx - halfStep);
          const width = Math.min(W - R - x, halfStep * 2);
          return (
            <rect
              key={`hit-${ci}`}
              className="hover-target"
              x={x}
              y={T}
              width={Math.max(1, width)}
              height={H - T - B}
              fill="transparent"
              {...hover({
                label: cat,
                rows: series.map((s, sIdx) => ({
                  swatch: paletteColor(sIdx),
                  name: s.name,
                  value: formatTick(s.data[ci]?.y ?? 0),
                })),
              })}
            />
          );
        })}
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
