import { useId, useMemo, useState } from "react";
import type { JSX, MouseEvent as ReactMouseEvent } from "react";

export interface SparklinePoint {
  readonly ts: string;
  readonly value: number;
}

export interface SparklineProps {
  readonly points: readonly SparklinePoint[];
  readonly width?: number;
  readonly height?: number;
  readonly formatTooltip?: (p: SparklinePoint) => string;
}

const FLAT_THRESHOLD_PCT = 0.0005;

export function Sparkline({
  points,
  width = 60,
  height = 16,
  formatTooltip,
}: SparklineProps): JSX.Element {
  const id = useId();
  const [hover, setHover] = useState<number | null>(null);

  const geometry = useMemo(() => {
    if (points.length === 0) {
      return { path: "", coords: [] as { x: number; y: number; p: SparklinePoint }[] };
    }
    const vals = points.map((p) => p.value);
    const minV = Math.min(...vals);
    const maxV = Math.max(...vals);
    const span = maxV - minV || 1;
    const n = points.length;
    const coords = points.map((p, i) => ({
      x: n === 1 ? width / 2 : (i / (n - 1)) * width,
      y: height - 2 - ((p.value - minV) / span) * (height - 4),
      p,
    }));
    const path = coords
      .map((c, i) => `${i === 0 ? "M" : "L"}${c.x.toFixed(2)},${c.y.toFixed(2)}`)
      .join(" ");
    return { path, coords };
  }, [points, width, height]);

  if (points.length === 0) {
    return (
      <span
        className="inline-block text-[--color-text-tertiary]"
        style={{ width, height, lineHeight: `${height}px` }}
        data-testid="sparkline-empty"
      >
        —
      </span>
    );
  }

  const first = points[0].value;
  const last = points[points.length - 1].value;
  const delta = first === 0 ? 0 : (last - first) / first;
  const color =
    Math.abs(delta) < FLAT_THRESHOLD_PCT
      ? "var(--color-text-tertiary)"
      : delta > 0
        ? "var(--color-feedback-success)"
        : "var(--color-feedback-error)";

  const findNearest = (xViewBox: number) => {
    let nearest = 0;
    let minDist = Math.abs(geometry.coords[0].x - xViewBox);
    for (let i = 1; i < geometry.coords.length; i++) {
      const d = Math.abs(geometry.coords[i].x - xViewBox);
      if (d < minDist) {
        minDist = d;
        nearest = i;
      }
    }
    return nearest;
  };

  const onMove = (e: ReactMouseEvent<SVGSVGElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (rect.width === 0) return;
    const xViewBox = ((e.clientX - rect.left) / rect.width) * width;
    setHover(findNearest(xViewBox));
  };

  const hoverPt = hover !== null ? geometry.coords[hover] : null;
  const tip =
    hoverPt && formatTooltip ? formatTooltip(hoverPt.p) : hoverPt?.p.value.toFixed(2);

  return (
    <span
      className="relative inline-block align-middle"
      style={{ width, height }}
      data-testid={`sparkline-${id}`}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        className="block h-full w-full"
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
      >
        <path
          d={geometry.path}
          fill="none"
          stroke={color}
          strokeWidth="1.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
        {hoverPt ? (
          <circle cx={hoverPt.x} cy={hoverPt.y} r={1.6} fill={color} />
        ) : null}
      </svg>
      {hoverPt && tip ? (
        <span
          role="status"
          className="pointer-events-none absolute -top-6 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded border border-[--color-border-subtle] bg-[--color-bg-elevated] px-1.5 py-[2px] font-mono text-[9px] text-[--color-text-primary] shadow"
          data-testid="sparkline-tooltip"
        >
          {tip}
        </span>
      ) : null}
    </span>
  );
}
