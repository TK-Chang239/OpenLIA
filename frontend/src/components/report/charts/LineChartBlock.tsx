import { useId, useMemo } from 'react';
import { paletteColor } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

export interface LineSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

export interface LineChartBlockProps {
  type: 'line_chart';
  title: string;
  // Canonical shape: ``categories: string[]`` + ``series[].values: number[]``.
  // Legacy ``series[].data: [{x, y}]`` shape is still accepted on read for
  // back-compat with reports persisted before the schema normalization.
  series: LineSeriesInput[];
  categories?: string[];
  x_label?: string;
  y_label?: string;
  options?: { show_legend?: boolean; show_grid?: boolean };
}

interface LineSeriesInput {
  name?: string;
  data?: unknown;
  values?: unknown;
}

function normalizeLineSeries(
  rawSeries: LineSeriesInput[] | undefined,
  rawCategories: string[] | undefined,
): { series: LineSeries[]; xs: string[] } {
  const list = Array.isArray(rawSeries) ? rawSeries : [];
  const declaredCats = Array.isArray(rawCategories) ? rawCategories.map(String) : [];

  // Capture x-axis labels from the first series shaped as ``data: [{x, y}]``
  // so we keep the legacy display unchanged.
  let derivedCats: string[] = [];
  if (declaredCats.length === 0) {
    const firstData = list[0]?.data;
    if (Array.isArray(firstData) && firstData.every((d) => d && typeof d === 'object' && 'x' in d)) {
      derivedCats = (firstData as { x: unknown }[]).map((d) => String(d.x));
    }
  }
  const xs = declaredCats.length > 0 ? declaredCats : derivedCats;

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

  // If categories weren't supplied either way, fall back to whatever the
  // first normalized series ended up exposing — keeps the legacy x-tick
  // rendering loop unchanged.
  const finalXs = xs.length > 0 ? xs : series[0]?.data.map((d) => String(d.x)) ?? [];
  return { series, xs: finalXs };
}

const W = 720;
const H = 220;
const PAD_L = 44;
const PAD_R = 16;
const PAD_T = 12;
const PAD_B = 28;

function niceTicks(min: number, max: number, count = 4): number[] {
  if (min === max) return [min];
  const span = max - min;
  const step = Math.pow(10, Math.floor(Math.log10(span / count)));
  const err = (count * step) / span;
  let mult = 1;
  if (err <= 0.15) mult = 10;
  else if (err <= 0.35) mult = 5;
  else if (err <= 0.75) mult = 2;
  const niceStep = mult * step;
  const niceMin = Math.floor(min / niceStep) * niceStep;
  const niceMax = Math.ceil(max / niceStep) * niceStep;
  const ticks: number[] = [];
  for (let v = niceMin; v <= niceMax + niceStep / 2; v += niceStep) ticks.push(Number(v.toFixed(8)));
  return ticks;
}

function formatTick(v: number): string {
  if (Math.abs(v) >= 1000) return `${(v / 1000).toFixed(1)}k`;
  if (Math.abs(v) >= 100) return v.toFixed(0);
  return v.toFixed(1);
}

function formatValue(v: number | undefined): string {
  if (v === undefined || v === null || Number.isNaN(v)) return '—';
  return formatTick(v);
}

export function LineChartBlock({
  title,
  series: rawSeries,
  categories: rawCategories,
  options,
}: LineChartBlockProps) {
  const { series, xs: normalizedXs } = useMemo(
    () => normalizeLineSeries(rawSeries, rawCategories),
    [rawSeries, rawCategories],
  );
  const chart = useMemo(() => {
    const xs = normalizedXs;
    const allY = series.flatMap((s) => s.data.map((d) => d.y));
    const minY = Math.min(...allY);
    const maxY = Math.max(...allY);
    const ticks = niceTicks(minY, maxY, 4);
    const yMin = ticks[0] ?? minY;
    const yMax = ticks[ticks.length - 1] ?? maxY;

    const xStep = xs.length > 1 ? (W - PAD_L - PAD_R) / (xs.length - 1) : 0;
    const yToPx = (y: number) =>
      yMax === yMin ? PAD_T + (H - PAD_T - PAD_B) / 2 : PAD_T + ((yMax - y) / (yMax - yMin)) * (H - PAD_T - PAD_B);

    return { xs, ticks, yMin, yMax, xStep, yToPx };
  }, [series, normalizedXs]);

  const showGrid = options?.show_grid !== false;
  const showLegend = options?.show_legend !== false;
  const gradId = useId().replace(/[^A-Za-z0-9_-]/g, '');
  const baselineY = H - PAD_B;
  const { figureRef, tooltipNode, hover, activeKey } = useChartTooltip();
  const activeIndex = typeof activeKey === 'number' ? activeKey : null;

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
        <defs>
          {series.map((_s, sIdx) => (
            <linearGradient
              key={sIdx}
              id={`${gradId}-${sIdx}`}
              x1="0"
              x2="0"
              y1="0"
              y2="1"
            >
              <stop offset="0%" stopColor={paletteColor(sIdx)} stopOpacity={0.32} />
              <stop offset="100%" stopColor={paletteColor(sIdx)} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        {showGrid &&
          chart.ticks.map((t) => (
            <g key={`tick-${t}`}>
              <line
                className="grid-line"
                x1={PAD_L}
                x2={W - PAD_R}
                y1={chart.yToPx(t)}
                y2={chart.yToPx(t)}
              />
              <text
                className="tick-label"
                x={PAD_L - 6}
                y={chart.yToPx(t)}
                dy="0.32em"
                textAnchor="end"
              >
                {formatTick(t)}
              </text>
            </g>
          ))}
        <line
          className="axis-line"
          x1={PAD_L}
          x2={W - PAD_R}
          y1={H - PAD_B}
          y2={H - PAD_B}
        />
        {chart.xs.map((label, i) => {
          if (chart.xs.length > 8 && i % 2 !== 0 && i !== chart.xs.length - 1) return null;
          const x = PAD_L + i * chart.xStep;
          return (
            <text
              key={`x-${i}`}
              className="tick-label"
              x={x}
              y={H - PAD_B + 14}
              textAnchor="middle"
            >
              {label}
            </text>
          );
        })}
        {series.map((s, sIdx) => {
          const color = paletteColor(sIdx);
          const coords = s.data.map((d, i) => [PAD_L + i * chart.xStep, chart.yToPx(d.y)] as const);
          const linePoints = coords.map(([x, y]) => `${x},${y}`).join(' ');
          const lastX = coords[coords.length - 1]?.[0] ?? PAD_L;
          const firstX = coords[0]?.[0] ?? PAD_L;
          const fillPath = `M${firstX},${baselineY} L${linePoints.replace(/\s/g, ' L')} L${lastX},${baselineY} Z`;
          return (
            <g key={s.name}>
              <path d={fillPath} fill={`url(#${gradId}-${sIdx})`} />
              <polyline
                className="series-line"
                points={linePoints}
                style={{ stroke: color }}
              />
              {s.data.map((d, i) => (
                <circle
                  key={i}
                  className={`series-dot${activeIndex === i ? ' series-dot--active' : ''}`}
                  cx={PAD_L + i * chart.xStep}
                  cy={chart.yToPx(d.y)}
                  r={activeIndex === i ? 4.5 : 2.5}
                  style={{ fill: color }}
                />
              ))}
            </g>
          );
        })}
        {activeIndex !== null && chart.xs[activeIndex] !== undefined ? (
          <line
            className="report-chart__guide"
            x1={PAD_L + activeIndex * chart.xStep}
            x2={PAD_L + activeIndex * chart.xStep}
            y1={PAD_T}
            y2={H - PAD_B}
          />
        ) : null}
        {chart.xs.map((label, i) => {
          const cx = PAD_L + i * chart.xStep;
          const halfStep = chart.xStep > 0 ? chart.xStep / 2 : (W - PAD_L - PAD_R) / 2;
          const x = Math.max(PAD_L, cx - halfStep);
          const width = Math.min(W - PAD_R - x, halfStep * 2);
          return (
            <rect
              key={`hit-${i}`}
              className="hover-target"
              x={x}
              y={PAD_T}
              width={Math.max(1, width)}
              height={H - PAD_T - PAD_B}
              fill="transparent"
              {...hover({
                key: i,
                label,
                rows: series.map((s, sIdx) => ({
                  swatch: paletteColor(sIdx),
                  name: s.name,
                  value: formatValue(s.data[i]?.y),
                })),
              })}
            />
          );
        })}
      </svg>
      {showLegend && series.length > 1 && (
        <div className="report-chart__legend">
          {series.map((s, sIdx) => (
            <span key={s.name}>
              <span
                className="report-chart__legend-swatch"
                style={{ background: paletteColor(sIdx) }}
              />
              {s.name}
            </span>
          ))}
        </div>
      )}
      {tooltipNode}
    </figure>
  );
}
