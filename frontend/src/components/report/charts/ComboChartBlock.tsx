import { useMemo } from 'react';
import { ChartEmpty } from "./ChartEmpty";
import { paletteColor, niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

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
  categories: rawCategories,
  bar_series: rawBarSeries,
  line_series: rawLineSeries,
  y_left_label,
  y_right_label,
  options,
}: ComboChartBlockProps) {
  const showLegend = options?.show_legend !== false;
  const showGrid = options?.show_grid !== false;
  const { figureRef, tooltipNode, hover, activeKey } = useChartTooltip();
  const activeIndex = typeof activeKey === 'number' ? activeKey : null;

  // LLM drift sometimes ships a series with ``data`` instead of ``values`` (the
  // key used by line/area charts). Coerce to a uniform shape so a single bad
  // series cannot crash the whole report view.
  const categories = useMemo<string[]>(
    () => (Array.isArray(rawCategories) ? rawCategories : []),
    [rawCategories],
  );
  const normalizeSeries = (raw: unknown): ComboSeries[] =>
    (Array.isArray(raw) ? raw : []).map((s) => {
      const obj = (s ?? {}) as { name?: unknown; values?: unknown; data?: unknown };
      const values = Array.isArray(obj.values)
        ? obj.values
        : Array.isArray(obj.data)
          ? obj.data
          : [];
      return {
        name: typeof obj.name === 'string' ? obj.name : '',
        values: (values as unknown[]).map((v) => (typeof v === 'number' ? v : 0)),
      };
    });
  const bar_series = useMemo<ComboSeries[]>(() => normalizeSeries(rawBarSeries), [rawBarSeries]);
  const line_series = useMemo<ComboSeries[]>(() => normalizeSeries(rawLineSeries), [rawLineSeries]);

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
        <ChartEmpty />
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
                  className={activeIndex === ci ? 'is-active' : undefined}
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

        {activeIndex !== null && categories[activeIndex] !== undefined ? (
          <line
            className="report-chart__guide"
            x1={L + activeIndex * slot + slot / 2}
            x2={L + activeIndex * slot + slot / 2}
            y1={T}
            y2={H - B}
          />
        ) : null}

        {line_series.map((s, si) => {
          const points = s.values.map((v, i) => `${L + i * slot + slot / 2},${yScale(v, chart.rMin, chart.rMax, T, H - B)}`).join(' ');
          const color = paletteColor(bar_series.length + si);
          return (
            <g key={s.name}>
              <polyline className="series-line" points={points} style={{ stroke: color }} />
              {s.values.map((v, i) => (
                <circle
                  key={i}
                  className={`series-dot${activeIndex === i ? ' series-dot--active' : ''}`}
                  cx={L + i * slot + slot / 2}
                  cy={yScale(v, chart.rMin, chart.rMax, T, H - B)}
                  r={activeIndex === i ? 4.5 : 2.5}
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
        {categories.map((cat, ci) => (
          <rect
            key={`hit-${ci}`}
            className="hover-target"
            x={L + ci * slot}
            y={T}
            width={Math.max(1, slot)}
            height={H - T - B}
            fill="transparent"
            {...hover({
              key: ci,
              label: cat,
              rows: [
                ...bar_series.map((s, si) => ({
                  swatch: paletteColor(si),
                  name: s.name,
                  value: formatTick(s.values[ci] ?? 0),
                })),
                ...line_series.map((s, si) => ({
                  swatch: paletteColor(bar_series.length + si),
                  name: s.name,
                  value: formatTick(s.values[ci] ?? 0),
                })),
              ],
            })}
          />
        ))}
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
      {tooltipNode}
    </figure>
  );
}
