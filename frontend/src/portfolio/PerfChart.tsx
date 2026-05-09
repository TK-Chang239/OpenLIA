import { useId, useRef, useState } from "react";
import type { JSX, MouseEvent as ReactMouseEvent } from "react";
import { motion } from "framer-motion";
import {
  PERF_PATHS,
  PERF_TABS,
  formatY,
  type PerfTab,
  type PerfPoint,
  xToLabel,
  xAxisLabels,
  yAxisLabels,
} from "./perfPaths";
import type { PerfRange } from "./PortfolioPageHeader";

export interface PerfChartProps {
  readonly range: PerfRange;
}

interface HoverState {
  point: PerfPoint;
  date: string;
  value: string;
}

const VIEWBOX_W = 800;
const VIEWBOX_H = 110;

/** The Portfolio page-level performance chart card.
 *  Tabs swap path geometries; range pills (driven by parent) seed the
 *  caption only — until PORTFOLIO_NAV_TIMESERIES_API ships, the same path
 *  geometry is reused across ranges. */
export function PerfChart({ range }: PerfChartProps): JSX.Element {
  const [tab, setTab] = useState<PerfTab>("NAV");
  const p = PERF_PATHS[tab];
  const gradId = useId();
  const clipId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  const yLabels = yAxisLabels(tab);
  const xLabels = xAxisLabels(range);

  const findNearest = (xViewBox: number): PerfPoint => {
    let nearest = p.points[0];
    let minDist = Math.abs(p.points[0].x - xViewBox);
    for (const pt of p.points) {
      const d = Math.abs(pt.x - xViewBox);
      if (d < minDist) {
        minDist = d;
        nearest = pt;
      }
    }
    return nearest;
  };

  const onMove = (e: ReactMouseEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) return;
    const xViewBox = ((e.clientX - rect.left) / rect.width) * VIEWBOX_W;
    const nearest = findNearest(xViewBox);
    setHover({
      point: nearest,
      date: xToLabel(nearest.x, range),
      value: formatY(tab, nearest.y),
    });
  };

  return (
    <section
      className="rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 pb-[14px] pt-[14px]"
      aria-label="Portfolio performance"
      data-testid="perf-chart"
    >
      <div className="mb-2 flex items-center gap-[14px]">
        {PERF_TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`cursor-pointer border-b pb-1 font-mono text-[10px] tracking-[0.08em] transition-colors ${
              tab === t
                ? "border-[--color-accent-primary] text-[--color-text-primary]"
                : "border-transparent text-[--color-text-tertiary] hover:text-[--color-text-secondary]"
            }`}
            aria-pressed={tab === t}
            data-testid={`perf-tab-${t}`}
          >
            {t}
          </button>
        ))}
        <span className="ml-auto cursor-default font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary]">
          {range} · placeholder series
        </span>
      </div>

      <div className="grid grid-cols-[40px_1fr] gap-x-2">
        <div
          className="flex flex-col justify-between py-[2px] text-right font-mono text-[9px] tracking-[0.04em] text-[--color-text-tertiary]"
          aria-hidden="true"
        >
          {yLabels.map((label) => (
            <span key={label}>{label}</span>
          ))}
        </div>

        <div>
          <div className="relative h-[110px]">
            <svg
              ref={svgRef}
              viewBox={`0 0 ${VIEWBOX_W} ${VIEWBOX_H}`}
              preserveAspectRatio="none"
              className="block h-full w-full"
              onMouseMove={onMove}
              onMouseLeave={() => setHover(null)}
            >
              <defs>
                <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                  <stop
                    offset="0%"
                    style={{
                      stopColor: "var(--color-accent-primary)",
                      stopOpacity: 0.32,
                    }}
                  />
                  <stop
                    offset="100%"
                    style={{
                      stopColor: "var(--color-accent-primary)",
                      stopOpacity: 0,
                    }}
                  />
                </linearGradient>
                <clipPath id={clipId}>
                  <motion.rect
                    key={`${tab}-${range}`}
                    x={0}
                    y={0}
                    height={VIEWBOX_H}
                    initial={{ width: 0 }}
                    animate={{ width: VIEWBOX_W }}
                    transition={{ duration: 0.9, ease: "easeOut" }}
                  />
                </clipPath>
              </defs>

              <g
                style={{ stroke: "var(--color-border-subtle)" }}
                strokeWidth="1"
                strokeDasharray="2 4"
              >
                <line x1="0" y1="22" x2={VIEWBOX_W} y2="22" />
                <line x1="0" y1="55" x2={VIEWBOX_W} y2="55" />
                <line x1="0" y1="88" x2={VIEWBOX_W} y2="88" />
              </g>

              <g clipPath={`url(#${clipId})`}>
                <path d={p.area} fill={`url(#${gradId})`} />
                <path
                  d={p.line}
                  fill="none"
                  style={{ stroke: "var(--yellow-600)" }}
                  strokeWidth="1.6"
                />
                <path
                  d={p.bench}
                  fill="none"
                  style={{ stroke: "var(--neutral-400)" }}
                  strokeWidth="1.2"
                  strokeDasharray="3 3"
                />
              </g>

              {hover ? (
                <line
                  x1={hover.point.x}
                  x2={hover.point.x}
                  y1={0}
                  y2={VIEWBOX_H}
                  style={{ stroke: "var(--color-text-tertiary)" }}
                  strokeWidth="1"
                  strokeDasharray="2 3"
                  pointerEvents="none"
                />
              ) : null}
            </svg>

            {hover ? (
              <HoverDotAndTooltip
                point={hover.point}
                date={hover.date}
                value={hover.value}
              />
            ) : null}
          </div>

          <div
            className="mt-2 flex justify-between font-mono text-[9px] tracking-[0.04em] text-[--color-text-tertiary]"
            aria-hidden="true"
          >
            {xLabels.map((label) => (
              <span key={label}>{label}</span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

interface HoverDotProps {
  point: PerfPoint;
  date: string;
  value: string;
}

/** Renders the dot + tooltip in HTML space so neither is squished by the
 *  SVG's `preserveAspectRatio="none"`. */
function HoverDotAndTooltip({ point, date, value }: HoverDotProps): JSX.Element {
  const leftPct = (point.x / VIEWBOX_W) * 100;
  const topPct = (point.y / VIEWBOX_H) * 100;
  const tooltipOnRight = leftPct < 18;
  return (
    <>
      <div
        className="pointer-events-none absolute h-[10px] w-[10px] -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[--color-bg-elevated] bg-[var(--yellow-600)] shadow-[0_0_0_1px_rgba(0,0,0,0.18)]"
        style={{ left: `${leftPct}%`, top: `${topPct}%` }}
        data-testid="perf-hover-dot"
      />
      <div
        className={`pointer-events-none absolute z-10 -translate-y-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-2 py-1 font-mono text-[10px] leading-tight text-[--color-text-primary] shadow-[0_4px_12px_rgba(0,0,0,0.08)] ${
          tooltipOnRight ? "translate-x-2" : "-translate-x-full -ml-2"
        }`}
        style={{ left: `${leftPct}%`, top: `calc(${topPct}% - 8px)` }}
        role="status"
        data-testid="perf-hover-tooltip"
      >
        <div className="text-[--color-text-tertiary]">{date}</div>
        <div className="text-[11px] font-semibold tabular-nums">{value}</div>
      </div>
    </>
  );
}
