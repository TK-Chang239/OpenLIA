/** Placeholder geometries for the Portfolio performance chart.
 *  Used by:
 *    - HomePortfolioGlanceCard (the Home dashboard mini chart)
 *    - PerfChart (the full-width Portfolio page chart)
 *    - HoldingDetailDrawer (the 200px per-holding mini chart)
 *
 *  All paths target a viewBox of 800 x 110 with `preserveAspectRatio="none"`.
 *  Replace with real series once PORTFOLIO_NAV_TIMESERIES_API ships. */

import type { PerfRange } from "./PortfolioPageHeader";

export const PERF_TABS = ["NAV", "vs SPX", "Drawdown", "Exposure"] as const;
export type PerfTab = (typeof PERF_TABS)[number];

export interface PerfPoint {
  x: number;
  y: number;
}

export interface PerfGeometry {
  area: string;
  line: string;
  bench: string;
  points: PerfPoint[];
  benchPoints: PerfPoint[];
}

const NAV_LINE: PerfPoint[] = [
  { x: 0, y: 90 },
  { x: 40, y: 86 },
  { x: 80, y: 82 },
  { x: 120, y: 88 },
  { x: 160, y: 72 },
  { x: 200, y: 76 },
  { x: 240, y: 64 },
  { x: 280, y: 68 },
  { x: 320, y: 52 },
  { x: 360, y: 58 },
  { x: 400, y: 44 },
  { x: 440, y: 48 },
  { x: 480, y: 38 },
  { x: 520, y: 42 },
  { x: 560, y: 30 },
  { x: 600, y: 34 },
  { x: 640, y: 24 },
  { x: 680, y: 28 },
  { x: 720, y: 16 },
  { x: 760, y: 18 },
  { x: 800, y: 10 },
];

const NAV_BENCH: PerfPoint[] = [
  { x: 0, y: 92 },
  { x: 40, y: 90 },
  { x: 80, y: 88 },
  { x: 120, y: 90 },
  { x: 160, y: 82 },
  { x: 200, y: 84 },
  { x: 240, y: 78 },
  { x: 280, y: 80 },
  { x: 320, y: 72 },
  { x: 360, y: 74 },
  { x: 400, y: 66 },
  { x: 440, y: 68 },
  { x: 480, y: 62 },
  { x: 520, y: 64 },
  { x: 560, y: 56 },
  { x: 600, y: 58 },
  { x: 640, y: 50 },
  { x: 680, y: 52 },
  { x: 720, y: 42 },
  { x: 760, y: 44 },
  { x: 800, y: 36 },
];

const VS_SPX_LINE: PerfPoint[] = [
  { x: 0, y: 80 },
  { x: 80, y: 78 },
  { x: 160, y: 68 },
  { x: 240, y: 70 },
  { x: 320, y: 58 },
  { x: 400, y: 62 },
  { x: 480, y: 46 },
  { x: 560, y: 50 },
  { x: 640, y: 32 },
  { x: 720, y: 28 },
  { x: 800, y: 18 },
];

const VS_SPX_BENCH: PerfPoint[] = [
  { x: 0, y: 84 },
  { x: 80, y: 84 },
  { x: 160, y: 80 },
  { x: 240, y: 82 },
  { x: 320, y: 76 },
  { x: 400, y: 74 },
  { x: 480, y: 68 },
  { x: 560, y: 68 },
  { x: 640, y: 60 },
  { x: 720, y: 58 },
  { x: 800, y: 50 },
];

const DRAWDOWN_LINE: PerfPoint[] = [
  { x: 0, y: 30 },
  { x: 80, y: 38 },
  { x: 160, y: 46 },
  { x: 240, y: 42 },
  { x: 320, y: 58 },
  { x: 400, y: 54 },
  { x: 480, y: 72 },
  { x: 560, y: 68 },
  { x: 640, y: 82 },
  { x: 720, y: 76 },
  { x: 800, y: 86 },
];

const DRAWDOWN_BENCH: PerfPoint[] = [
  { x: 0, y: 40 },
  { x: 80, y: 46 },
  { x: 160, y: 52 },
  { x: 240, y: 50 },
  { x: 320, y: 62 },
  { x: 400, y: 60 },
  { x: 480, y: 72 },
  { x: 560, y: 70 },
  { x: 640, y: 80 },
  { x: 720, y: 78 },
  { x: 800, y: 86 },
];

const EXPOSURE_LINE: PerfPoint[] = [
  { x: 0, y: 60 },
  { x: 80, y: 56 },
  { x: 160, y: 64 },
  { x: 240, y: 52 },
  { x: 320, y: 58 },
  { x: 400, y: 46 },
  { x: 480, y: 50 },
  { x: 560, y: 38 },
  { x: 640, y: 44 },
  { x: 720, y: 30 },
  { x: 800, y: 36 },
];

const EXPOSURE_BENCH: PerfPoint[] = [
  { x: 0, y: 68 },
  { x: 80, y: 66 },
  { x: 160, y: 72 },
  { x: 240, y: 62 },
  { x: 320, y: 66 },
  { x: 400, y: 58 },
  { x: 480, y: 60 },
  { x: 560, y: 50 },
  { x: 640, y: 54 },
  { x: 720, y: 44 },
  { x: 800, y: 48 },
];

function toLine(points: PerfPoint[]): string {
  return points
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`)
    .join(" ");
}

function toArea(points: PerfPoint[]): string {
  const head = toLine(points);
  const last = points[points.length - 1];
  const first = points[0];
  return `${head} L${last.x},110 L${first.x},110 Z`;
}

function build(line: PerfPoint[], bench: PerfPoint[]): PerfGeometry {
  return {
    area: toArea(line),
    line: toLine(line),
    bench: toLine(bench),
    points: line,
    benchPoints: bench,
  };
}

export const PERF_PATHS: Record<PerfTab, PerfGeometry> = {
  NAV: build(NAV_LINE, NAV_BENCH),
  "vs SPX": build(VS_SPX_LINE, VS_SPX_BENCH),
  Drawdown: build(DRAWDOWN_LINE, DRAWDOWN_BENCH),
  Exposure: build(EXPOSURE_LINE, EXPOSURE_BENCH),
};

/** Top-of-chart, mid-chart, and bottom-of-chart y-axis labels per tab.
 *  Returned in chart order (top first). Placeholders only — replace once a
 *  real series is wired. */
export function yAxisLabels(tab: PerfTab): readonly [string, string, string] {
  switch (tab) {
    case "NAV":
      return ["$120k", "$80k", "$40k"];
    case "vs SPX":
      return ["+12%", "+5%", "-2%"];
    case "Drawdown":
      return ["0%", "-5%", "-10%"];
    case "Exposure":
      return ["110%", "70%", "30%"];
  }
}

/** Format the y-value at the hovered point as a placeholder readout. */
export function formatY(tab: PerfTab, y: number): string {
  const t = Math.max(0, Math.min(1, 1 - y / 110));
  switch (tab) {
    case "NAV":
      return `$${(40 + t * 80).toFixed(1)}k`;
    case "vs SPX": {
      const v = -2 + t * 14;
      return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
    }
    case "Drawdown":
      return `${(-10 + t * 10).toFixed(2)}%`;
    case "Exposure":
      return `${Math.round(30 + t * 80)}%`;
  }
}

/** Evenly-spaced x-axis label set per range (placeholder). */
export function xAxisLabels(range: PerfRange): readonly string[] {
  switch (range) {
    case "1D":
      return ["09:30", "11:00", "12:30", "14:00", "15:30"];
    case "1W":
      return ["Mon", "Tue", "Wed", "Thu", "Fri"];
    case "1M":
      return ["Wk 1", "Wk 2", "Wk 3", "Wk 4"];
    case "3M":
      return ["M-3", "M-2", "M-1", "Now"];
    case "6M":
      return ["M-6", "M-4", "M-2", "Now"];
    case "YTD":
      return ["Jan", "Mar", "May", "Jul", "Sep", "Nov"];
    case "1Y":
      return ["Q1", "Q2", "Q3", "Q4"];
    case "5Y":
      return ["'22", "'23", "'24", "'25", "'26"];
  }
}

/** Map a viewBox-x position to a placeholder date/time string for the tooltip. */
export function xToLabel(x: number, range: PerfRange): string {
  const labels = xAxisLabels(range);
  const idx = Math.min(
    labels.length - 1,
    Math.max(0, Math.round((x / 800) * (labels.length - 1))),
  );
  return labels[idx];
}
