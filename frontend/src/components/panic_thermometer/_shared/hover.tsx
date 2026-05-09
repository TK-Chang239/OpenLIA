import type { JSX } from "react";
import { useCallback, useRef, useState } from "react";

export interface ChartHoverPoint {
  index: number;
  xPx: number;
  yPx: number;
  label: string;
  value: string;
}

interface UseChartHoverOpts<T> {
  points: T[];
  toX: (i: number) => number;
  toY: (point: T, i: number) => number;
  label: (point: T, i: number) => string;
  value: (point: T, i: number) => string;
  /** SVG viewBox width — used to map mouse coords back into viewBox space. */
  viewWidth: number;
  /** SVG viewBox x range where points exist (for snapping). */
  xMin: number;
  xMax: number;
}

export interface ChartHoverState<T> {
  hovered: ChartHoverPoint | null;
  onMouseMove: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseLeave: () => void;
  svgRef: React.RefObject<SVGSVGElement>;
  /** raw data accessors */
  data: T[];
}

export function useChartHover<T>(opts: UseChartHoverOpts<T>): ChartHoverState<T> {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hovered, setHovered] = useState<ChartHoverPoint | null>(null);

  const onMouseMove = useCallback(
    (e: React.MouseEvent<SVGSVGElement>) => {
      const svg = svgRef.current;
      if (!svg) return;
      const rect = svg.getBoundingClientRect();
      // Map screen px to viewBox space.
      const xRel = ((e.clientX - rect.left) / rect.width) * opts.viewWidth;
      // Find nearest data point's x.
      let bestIdx = 0;
      let bestDist = Infinity;
      for (let i = 0; i < opts.points.length; i++) {
        const px = opts.toX(i);
        const d = Math.abs(px - xRel);
        if (d < bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      const p = opts.points[bestIdx];
      setHovered({
        index: bestIdx,
        xPx: opts.toX(bestIdx),
        yPx: opts.toY(p, bestIdx),
        label: opts.label(p, bestIdx),
        value: opts.value(p, bestIdx),
      });
    },
    [opts],
  );

  const onMouseLeave = useCallback(() => setHovered(null), []);

  return { hovered, onMouseMove, onMouseLeave, svgRef, data: opts.points };
}

interface CrosshairProps {
  hovered: ChartHoverPoint | null;
  yMin: number;
  yMax: number;
  xMin: number;
  xMax: number;
  /** show the crosshair line vertically across plot area */
  showLine?: boolean;
  /** show the highlight dot at the snapped point */
  showDot?: boolean;
  dotColor?: string;
  lineColor?: string;
}

export function Crosshair({
  hovered,
  yMin,
  yMax,
  xMin,
  xMax,
  showLine = true,
  showDot = true,
  dotColor = "var(--color-text-primary)",
  lineColor = "var(--color-text-primary)",
}: CrosshairProps): JSX.Element | null {
  if (!hovered) return null;
  if (hovered.xPx < xMin || hovered.xPx > xMax) return null;
  return (
    <g pointerEvents="none">
      {showLine ? (
        <line
          x1={hovered.xPx}
          y1={yMin}
          x2={hovered.xPx}
          y2={yMax}
          stroke={lineColor}
          strokeWidth={0.8}
          strokeDasharray="2 2"
          opacity={0.5}
        />
      ) : null}
      {showDot ? (
        <circle
          cx={hovered.xPx}
          cy={hovered.yPx}
          r={4.5}
          fill={dotColor}
          stroke="var(--color-bg-elevated)"
          strokeWidth={1.5}
        />
      ) : null}
    </g>
  );
}

/** HTML tooltip layered above SVG via an absolutely-positioned overlay. */
export function HoverTooltip({
  hovered,
  hostRect,
}: {
  hovered: ChartHoverPoint | null;
  /** Bounding rect of the SVG host for positioning. */
  hostRect: { width: number; height: number };
}): JSX.Element | null {
  if (!hovered) return null;
  const xPct = (hovered.xPx / hostRect.width) * 100;
  const yPct = (hovered.yPx / hostRect.height) * 100;
  // Flip horizontally if near right edge.
  const flipX = xPct > 70;
  return (
    <div
      role="tooltip"
      className="pt-tooltip"
      style={{
        position: "absolute",
        left: `${xPct}%`,
        top: `${yPct}%`,
        transform: `translate(${flipX ? "calc(-100% - 12px)" : "12px"}, -50%)`,
        pointerEvents: "none",
      }}
    >
      <div className="pt-tooltip-label">{hovered.label}</div>
      <div className="pt-tooltip-value">{hovered.value}</div>
    </div>
  );
}
