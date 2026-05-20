import { useMemo } from 'react';
import { ChartEmpty } from "./ChartEmpty";
import { niceTicks, formatTick, yScale, visibleXLabels, CHART_VIEWBOX, CHART_PADDING } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

export interface CandleRow { date: string; open: number; high: number; low: number; close: number; }
export interface VolumeRow { date: string; value: number; }

export interface CandlestickBlockProps {
  type: 'candlestick_chart';
  title: string;
  data: CandleRow[];
  volume?: VolumeRow[];
  options?: { show_grid?: boolean };
}

const { W, H } = CHART_VIEWBOX;
const { L, R, T, B } = CHART_PADDING;

export function CandlestickBlock({ title, data, volume, options }: CandlestickBlockProps) {
  const showGrid = options?.show_grid !== false;
  const { figureRef, tooltipNode, hover } = useChartTooltip();

  const chart = useMemo(() => {
    if (data.length === 0) return null;
    const lows = data.map((d) => d.low);
    const highs = data.map((d) => d.high);
    const ticks = niceTicks(Math.min(...lows), Math.max(...highs), 4);
    const yMin = ticks[0]!;
    const yMax = ticks[ticks.length - 1]!;
    const slot = (W - L - R) / data.length;
    const candleW = Math.max(2, slot * 0.62);
    const volMax = volume && volume.length ? Math.max(...volume.map((v) => v.value)) : 0;
    return { ticks, yMin, yMax, slot, candleW, volMax };
  }, [data, volume]);

  if (!chart) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <ChartEmpty />
      </figure>
    );
  }

  const visibleX = visibleXLabels(data.map((d) => d.date));
  const volH = volume && volume.length ? 30 : 0;
  const priceBottom = H - B - volH;

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
            const y = yScale(t, chart.yMin, chart.yMax, T, priceBottom);
            return (
              <g key={`tick-${t}`}>
                <line className="grid-line" x1={L} x2={W - R} y1={y} y2={y} />
                <text className="tick-label" x={L - 6} y={y} dy="0.32em" textAnchor="end">
                  {formatTick(t)}
                </text>
              </g>
            );
          })}
        <line className="axis-line" x1={L} x2={W - R} y1={priceBottom} y2={priceBottom} />

        {data.map((d, i) => {
          const cx = L + i * chart.slot + chart.slot / 2;
          const yOpen = yScale(d.open, chart.yMin, chart.yMax, T, priceBottom);
          const yClose = yScale(d.close, chart.yMin, chart.yMax, T, priceBottom);
          const yHigh = yScale(d.high, chart.yMin, chart.yMax, T, priceBottom);
          const yLow = yScale(d.low, chart.yMin, chart.yMax, T, priceBottom);
          const up = d.close >= d.open;
          const fill = up ? 'var(--report-positive)' : 'var(--report-negative)';
          return (
            <g key={d.date}>
              <line x1={cx} x2={cx} y1={yHigh} y2={yLow} style={{ stroke: fill, strokeWidth: 1 }} />
              <rect
                x={cx - chart.candleW / 2}
                y={Math.min(yOpen, yClose)}
                width={chart.candleW}
                height={Math.max(1, Math.abs(yOpen - yClose))}
                style={{ fill, stroke: fill, strokeWidth: 1 }}
              />
            </g>
          );
        })}

        {volume && volume.length
          ? volume.map((v, i) => {
              const x = L + i * chart.slot + (chart.slot - chart.candleW) / 2;
              const h = chart.volMax > 0 ? (v.value / chart.volMax) * (volH - 6) : 0;
              const up = i === 0 || v.value >= (volume[i - 1]?.value ?? v.value);
              return (
                <rect
                  key={v.date}
                  x={x}
                  y={priceBottom + (volH - h)}
                  width={chart.candleW}
                  height={h}
                  style={{ fill: up ? 'var(--report-text-secondary)' : 'var(--report-text-tertiary)', opacity: 0.6 }}
                />
              );
            })
          : null}

        {data.map((d, i) =>
          visibleX[i] ? (
            <text
              key={`x-${i}`}
              className="tick-label"
              x={L + i * chart.slot + chart.slot / 2}
              y={H - B + 14}
              textAnchor="middle"
            >
              {d.date}
            </text>
          ) : null,
        )}
        {data.map((d, i) => {
          const v = volume?.[i]?.value;
          return (
            <rect
              key={`hit-${d.date}`}
              className="hover-target"
              x={L + i * chart.slot}
              y={T}
              width={Math.max(1, chart.slot)}
              height={H - T - B}
              fill="transparent"
              {...hover({
                label: d.date,
                rows: [
                  { name: 'Open', value: formatTick(d.open) },
                  { name: 'High', value: formatTick(d.high) },
                  { name: 'Low', value: formatTick(d.low) },
                  { name: 'Close', value: formatTick(d.close) },
                  ...(v !== undefined ? [{ name: 'Volume', value: formatTick(v) }] : []),
                ],
              })}
            />
          );
        })}
      </svg>
      {tooltipNode}
    </figure>
  );
}
