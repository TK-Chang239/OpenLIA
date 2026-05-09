import { useMemo } from 'react';
import { niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';

type ItemType = 'total' | 'increase' | 'decrease';

export interface WaterfallItem { label: string; value: number; type: ItemType; }

export interface WaterfallBlockProps {
  type: 'waterfall_chart';
  title: string;
  items: WaterfallItem[];
  options?: { show_grid?: boolean };
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;

export function WaterfallBlock({ title, items, options }: WaterfallBlockProps) {
  const showGrid = options?.show_grid !== false;

  const chart = useMemo(() => {
    if (items.length === 0) return null;
    let running = 0;
    const bars = items.map((it) => {
      if (it.type === 'total') {
        running = it.value;
        return { ...it, lo: 0, hi: it.value };
      }
      if (it.type === 'increase') {
        const lo = running;
        running += it.value;
        return { ...it, lo, hi: running };
      }
      const hi = running;
      running -= it.value;
      return { ...it, lo: running, hi };
    });
    const all = bars.flatMap((b) => [b.lo, b.hi]).concat([0]);
    const ticks = niceTicks(Math.min(...all), Math.max(...all), 4);
    return { bars, ticks, yMin: ticks[0]!, yMax: ticks[ticks.length - 1]! };
  }, [items]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  const slot = (W - L - R) / chart.bars.length;
  const barW = Math.max(2, slot * 0.62);
  const visibleX = visibleXLabels(chart.bars.map((b) => b.label));

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

        {chart.bars.map((b, i) => {
          const x = L + i * slot + (slot - barW) / 2;
          const yHi = yScale(b.hi, chart.yMin, chart.yMax, T, H - B);
          const yLo = yScale(b.lo, chart.yMin, chart.yMax, T, H - B);
          const y = Math.min(yHi, yLo);
          const h = Math.max(1, Math.abs(yHi - yLo));
          const fill =
            b.type === 'total'
              ? 'var(--report-text-primary)'
              : b.type === 'increase'
              ? 'var(--report-positive)'
              : 'var(--report-negative)';
          return (
            <g key={b.label}>
              <rect x={x} y={y} width={barW} height={h} style={{ fill }} />
              {i < chart.bars.length - 1 && b.type !== 'total' ? (
                <line
                  x1={x + barW}
                  x2={L + (i + 1) * slot + (slot - barW) / 2}
                  y1={yScale(b.hi, chart.yMin, chart.yMax, T, H - B)}
                  y2={yScale(b.hi, chart.yMin, chart.yMax, T, H - B)}
                  style={{ stroke: 'var(--report-border-strong)', strokeDasharray: '2 3', strokeWidth: 1 }}
                />
              ) : null}
            </g>
          );
        })}

        {chart.bars.map((b, i) =>
          visibleX[i] ? (
            <text
              key={`x-${i}`}
              className="tick-label"
              x={L + i * slot + slot / 2}
              y={H - B + 14}
              textAnchor="middle"
            >
              {b.label}
            </text>
          ) : null,
        )}
      </svg>
    </figure>
  );
}
