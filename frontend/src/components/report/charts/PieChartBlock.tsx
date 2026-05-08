import { useMemo } from 'react';
import { paletteColor, formatTick } from './svgUtils';

export interface PieSegment {
  label: string;
  value: number;
}

export interface PieChartBlockProps {
  type: 'pie_chart';
  title: string;
  segments: PieSegment[];
  donut?: boolean;
  options?: { show_legend?: boolean };
}

const SIZE = 220;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R_OUTER = 96;

export function PieChartBlock({
  title,
  segments,
  donut = false,
  options,
}: PieChartBlockProps) {
  const showLegend = options?.show_legend !== false;
  const total = segments.reduce((acc, s) => acc + s.value, 0) || 1;
  const rInner = donut ? R_OUTER * 0.6 : 0;

  const arcs = useMemo(() => {
    let acc = 0;
    return segments.map((s) => {
      const startA = (acc / total) * Math.PI * 2 - Math.PI / 2;
      acc += s.value;
      const endA = (acc / total) * Math.PI * 2 - Math.PI / 2;
      return { ...s, startA, endA, fraction: s.value / total };
    });
  }, [segments, total]);

  return (
    <figure className="report-chart">
      <figcaption className="report-chart__title">{title}</figcaption>
      <div className="report-pie">
        <svg
          className="report-pie__svg"
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={title}
        >
          {arcs.map((a, i) => (
            <path
              key={a.label}
              d={arcPath(CX, CY, R_OUTER, rInner, a.startA, a.endA, a.fraction)}
              style={{ fill: paletteColor(i) }}
            />
          ))}
        </svg>
        {showLegend ? (
          <ul className="report-pie__legend">
            {arcs.map((a, i) => (
              <li key={a.label}>
                <span
                  className="report-pie__swatch"
                  style={{ background: paletteColor(i) }}
                />
                <span className="report-pie__label">{a.label}</span>
                <span className="report-pie__value">
                  {formatTick(a.value)} <em>{(a.fraction * 100).toFixed(1)}%</em>
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </figure>
  );
}

function arcPath(
  cx: number,
  cy: number,
  rOuter: number,
  rInner: number,
  startA: number,
  endA: number,
  fraction: number,
): string {
  if (fraction <= 0) return '';
  const fullCircle = fraction >= 0.999;
  const largeArc = endA - startA > Math.PI ? 1 : 0;
  const ox1 = cx + rOuter * Math.cos(startA);
  const oy1 = cy + rOuter * Math.sin(startA);
  const ox2 = cx + rOuter * Math.cos(endA);
  const oy2 = cy + rOuter * Math.sin(endA);
  if (rInner <= 0) {
    if (fullCircle) {
      return `M ${cx - rOuter},${cy} a ${rOuter},${rOuter} 0 1 0 ${rOuter * 2},0 a ${rOuter},${rOuter} 0 1 0 ${-rOuter * 2},0 Z`;
    }
    return `M ${cx},${cy} L ${ox1},${oy1} A ${rOuter},${rOuter} 0 ${largeArc} 1 ${ox2},${oy2} Z`;
  }
  const ix1 = cx + rInner * Math.cos(endA);
  const iy1 = cy + rInner * Math.sin(endA);
  const ix2 = cx + rInner * Math.cos(startA);
  const iy2 = cy + rInner * Math.sin(startA);
  if (fullCircle) {
    return [
      `M ${cx - rOuter},${cy}`,
      `a ${rOuter},${rOuter} 0 1 0 ${rOuter * 2},0`,
      `a ${rOuter},${rOuter} 0 1 0 ${-rOuter * 2},0`,
      `M ${cx - rInner},${cy}`,
      `a ${rInner},${rInner} 0 1 1 ${rInner * 2},0`,
      `a ${rInner},${rInner} 0 1 1 ${-rInner * 2},0 Z`,
    ].join(' ');
  }
  return [
    `M ${ox1},${oy1}`,
    `A ${rOuter},${rOuter} 0 ${largeArc} 1 ${ox2},${oy2}`,
    `L ${ix1},${iy1}`,
    `A ${rInner},${rInner} 0 ${largeArc} 0 ${ix2},${iy2}`,
    'Z',
  ].join(' ');
}
