import { useId, useMemo, useRef, useState } from "react";
import type { JSX, MouseEvent as ReactMouseEvent } from "react";
import { motion } from "framer-motion";
import type { ValueSeriesResponse } from "../api/portfolio";
import type { PerfRange } from "./PortfolioPageHeader";

export interface PerfChartProps {
  readonly range: PerfRange;
  readonly series: ValueSeriesResponse | null;
  readonly loading: boolean;
}

interface HoverState {
  x: number;
  y: number;
  date: string;
  value: string;
}

const VIEWBOX_W = 800;
const VIEWBOX_H = 110;

function fmtUsd(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const abs = Math.abs(n);
  if (abs >= 1_000_000) return `${n < 0 ? "-" : ""}$${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${n < 0 ? "-" : ""}$${(abs / 1_000).toFixed(2)}k`;
  return `${n < 0 ? "-" : ""}$${abs.toFixed(2)}`;
}

function formatLabel(p: { date: string; ts: string | null }): string {
  if (p.ts) {
    const d = new Date(p.ts);
    if (!Number.isNaN(d.getTime())) {
      const hh = String(d.getHours()).padStart(2, "0");
      const mm = String(d.getMinutes()).padStart(2, "0");
      return `${hh}:${mm}`;
    }
  }
  return p.date;
}

function pickXLabels(
  points: { date: string; ts: string | null }[],
  count: number,
): string[] {
  if (points.length === 0) return [];
  const out: string[] = [];
  const step = Math.max(1, Math.floor((points.length - 1) / (count - 1)));
  for (let i = 0; i < points.length; i += step) out.push(formatLabel(points[i]));
  if (out.length < count && points.length > 1)
    out.push(formatLabel(points[points.length - 1]));
  return out.slice(0, count);
}

export function PerfChart({ range, series, loading }: PerfChartProps): JSX.Element {
  const gradId = useId();
  const clipId = useId();
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [hover, setHover] = useState<HoverState | null>(null);

  const points = useMemo(() => {
    if (!series || series.points.length === 0)
      return [] as {
        date: string;
        ts: string | null;
        value: number;
        x: number;
        y: number;
      }[];
    const values = series.points.map((p) => Number(p.value));
    const minV = Math.min(...values);
    const maxV = Math.max(...values);
    const span = maxV - minV || 1;
    const n = series.points.length;
    return series.points.map((p, i) => {
      const v = Number(p.value);
      return {
        date: p.date,
        ts: p.ts,
        value: v,
        x: n === 1 ? VIEWBOX_W / 2 : (i / (n - 1)) * VIEWBOX_W,
        y: VIEWBOX_H - 8 - ((v - minV) / span) * (VIEWBOX_H - 16),
      };
    });
  }, [series]);

  const linePath = useMemo(() => {
    if (points.length === 0) return "";
    return points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
  }, [points]);

  const areaPath = useMemo(() => {
    if (points.length === 0) return "";
    const head = linePath;
    const last = points[points.length - 1];
    const first = points[0];
    return `${head} L${last.x.toFixed(2)},${VIEWBOX_H} L${first.x.toFixed(2)},${VIEWBOX_H} Z`;
  }, [points, linePath]);

  const yLabels = useMemo(() => {
    if (points.length === 0) return ["—", "—", "—"] as const;
    const vals = points.map((p) => p.value);
    const minV = Math.min(...vals);
    const maxV = Math.max(...vals);
    return [fmtUsd(maxV), fmtUsd((minV + maxV) / 2), fmtUsd(minV)] as const;
  }, [points]);

  const xLabels = useMemo(() => pickXLabels(points, 5), [points]);

  const findNearest = (xViewBox: number) => {
    if (points.length === 0) return null;
    let nearest = points[0];
    let minDist = Math.abs(points[0].x - xViewBox);
    for (const pt of points) {
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
    if (!svg || points.length === 0) return;
    const rect = svg.getBoundingClientRect();
    if (rect.width === 0) return;
    const xViewBox = ((e.clientX - rect.left) / rect.width) * VIEWBOX_W;
    const nearest = findNearest(xViewBox);
    if (!nearest) return;
    setHover({
      x: nearest.x,
      y: nearest.y,
      date: formatLabel(nearest),
      value: fmtUsd(nearest.value),
    });
  };

  const empty = !loading && points.length === 0;

  return (
    <section
      className="rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 pb-[14px] pt-[14px]"
      aria-label="Portfolio performance"
      data-testid="perf-chart"
    >
      <div className="mb-2 flex items-center gap-[14px]">
        <span className="font-mono text-[10px] tracking-[0.08em] text-[--color-text-primary]">NAV</span>
        <span className="ml-auto cursor-default font-mono text-[10px] tracking-[0.08em] text-[--color-text-tertiary]">
          {range}
          {series?.actual_span ? ` · ${series.actual_span.start} → ${series.actual_span.end}` : ""}
        </span>
      </div>

      <div className="grid grid-cols-[50px_1fr] gap-x-2">
        <div
          className="flex flex-col justify-between py-[2px] text-right font-mono text-[9px] tracking-[0.04em] text-[--color-text-tertiary]"
          aria-hidden="true"
        >
          {yLabels.map((label, i) => (
            <span key={i}>{label}</span>
          ))}
        </div>

        <div>
          <div className="relative h-[110px]">
            {empty ? (
              <div className="flex h-full items-center justify-center font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                No data for {range}
              </div>
            ) : loading ? (
              <div className="h-full w-full animate-pulse rounded bg-[--color-border-subtle]/30" />
            ) : (
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
                    <stop offset="0%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0.32 }} />
                    <stop offset="100%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0 }} />
                  </linearGradient>
                  <clipPath id={clipId}>
                    <motion.rect
                      key={`${range}-${points.length}`}
                      x={0}
                      y={0}
                      height={VIEWBOX_H}
                      initial={{ width: 0 }}
                      animate={{ width: VIEWBOX_W }}
                      transition={{ duration: 0.9, ease: "easeOut" }}
                    />
                  </clipPath>
                </defs>

                <g style={{ stroke: "var(--color-border-subtle)" }} strokeWidth="1" strokeDasharray="2 4">
                  <line x1="0" y1="22" x2={VIEWBOX_W} y2="22" />
                  <line x1="0" y1="55" x2={VIEWBOX_W} y2="55" />
                  <line x1="0" y1="88" x2={VIEWBOX_W} y2="88" />
                </g>

                <g clipPath={`url(#${clipId})`}>
                  <path d={areaPath} fill={`url(#${gradId})`} />
                  <path d={linePath} fill="none" style={{ stroke: "var(--yellow-600)" }} strokeWidth="1.6" />
                </g>

                {hover ? (
                  <line
                    x1={hover.x}
                    x2={hover.x}
                    y1={0}
                    y2={VIEWBOX_H}
                    style={{ stroke: "var(--color-text-tertiary)" }}
                    strokeWidth="1"
                    strokeDasharray="2 3"
                    pointerEvents="none"
                  />
                ) : null}
              </svg>
            )}

            {hover && !empty && !loading ? (
              <HoverDotAndTooltip x={hover.x} y={hover.y} date={hover.date} value={hover.value} />
            ) : null}
          </div>

          <div
            className="mt-2 flex justify-between font-mono text-[9px] tracking-[0.04em] text-[--color-text-tertiary]"
            aria-hidden="true"
          >
            {xLabels.length > 0
              ? xLabels.map((label, i) => <span key={`${label}-${i}`}>{label}</span>)
              : null}
          </div>
        </div>
      </div>
    </section>
  );
}

function HoverDotAndTooltip({
  x,
  y,
  date,
  value,
}: {
  x: number;
  y: number;
  date: string;
  value: string;
}): JSX.Element {
  const leftPct = (x / VIEWBOX_W) * 100;
  const topPct = (y / VIEWBOX_H) * 100;
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
