import { useMemo } from 'react';
import { CHART_VIEWBOX } from './svgUtils';
import { useChartTooltip } from './useChartTooltip';

export interface HeatmapBlockProps {
  type: 'heatmap';
  title: string;
  x_labels: string[];
  y_labels: string[];
  values: number[][];
  options?: { show_legend?: boolean };
}

const { W } = CHART_VIEWBOX;

export function HeatmapBlock({ title, x_labels, y_labels, values, options }: HeatmapBlockProps) {
  const showLegend = options?.show_legend !== false;
  const { figureRef, tooltipNode, hover } = useChartTooltip();

  const flat = useMemo(() => {
    const out: number[] = [];
    for (const row of values) for (const v of row) out.push(v);
    return out;
  }, [values]);

  if (flat.length === 0) {
    return (
      <figure className="report-chart">
        <figcaption className="report-chart__title">{title}</figcaption>
        <div className="report-chart__empty">No data</div>
      </figure>
    );
  }

  const minV = Math.min(...flat);
  const maxV = Math.max(...flat);
  const range = maxV - minV || 1;
  const padL = 64;
  const padT = 8;
  const cellW = (W - padL - 16) / Math.max(1, x_labels.length);
  const cellH = 24;
  const totalH = padT + y_labels.length * cellH + 28;

  const tone = (v: number) => {
    const t = (v - minV) / range;
    return `rgba(212, 255, 0, ${0.1 + t * 0.85})`;
  };

  return (
    <figure className="report-chart" ref={figureRef}>
      <figcaption className="report-chart__title">{title}</figcaption>
      <svg
        className="report-line-chart"
        viewBox={`0 0 ${W} ${totalH}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={title}
      >
        {y_labels.map((yl, yi) => (
          <g key={yl}>
            <text
              className="tick-label"
              x={padL - 8}
              y={padT + yi * cellH + cellH / 2}
              dy="0.32em"
              textAnchor="end"
            >
              {yl}
            </text>
            {x_labels.map((xl, xi) => {
              const v = values[yi]?.[xi] ?? 0;
              return (
                <g key={`${yi}-${xi}`}>
                  <rect
                    className="hover-target"
                    x={padL + xi * cellW}
                    y={padT + yi * cellH}
                    width={cellW - 1}
                    height={cellH - 1}
                    style={{ fill: tone(v), stroke: 'var(--report-border)', strokeWidth: 0.5 }}
                    {...hover({
                      label: `${yl} · ${xl}`,
                      rows: [{ name: 'Value', value: Number.isFinite(v) ? v.toFixed(3) : '—' }],
                    })}
                  />
                  <text
                    x={padL + xi * cellW + cellW / 2}
                    y={padT + yi * cellH + cellH / 2}
                    dy="0.32em"
                    textAnchor="middle"
                    style={{ fill: 'var(--report-text-primary)', fontFamily: 'var(--report-font-mono)', fontSize: 10 }}
                  >
                    {Number.isFinite(v) ? v.toFixed(2) : ''}
                  </text>
                </g>
              );
            })}
          </g>
        ))}
        {x_labels.map((xl, xi) => (
          <text
            key={xl}
            className="tick-label"
            x={padL + xi * cellW + cellW / 2}
            y={padT + y_labels.length * cellH + 14}
            textAnchor="middle"
          >
            {xl}
          </text>
        ))}
      </svg>
      {showLegend ? (
        <div className="report-chart__legend">
          <span>
            <span className="report-chart__legend-swatch" style={{ background: 'rgba(212,255,0,0.1)' }} />
            min {minV.toFixed(2)}
          </span>
          <span>
            <span className="report-chart__legend-swatch" style={{ background: 'rgba(212,255,0,0.95)' }} />
            max {maxV.toFixed(2)}
          </span>
        </div>
      ) : null}
      {tooltipNode}
    </figure>
  );
}
