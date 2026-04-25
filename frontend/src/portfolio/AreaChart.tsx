import { useId, useMemo } from "react";

export interface AreaChartProps {
  readonly values: readonly number[];
  readonly width?: number;
  readonly height?: number;
  readonly className?: string;
}

/**
 * AreaChart — inline SVG area + line chart used by the card view.
 * Up trend renders green, down trend red.
 */
export function AreaChart({
  values,
  width = 240,
  height = 100,
  className,
}: AreaChartProps): JSX.Element {
  const gid = useId().replace(/[^a-zA-Z0-9_-]/g, "");
  const { line, area, tone } = useMemo(() => {
    if (values.length < 2) {
      return { line: "", area: "", tone: "var(--color-feedback-success)" };
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const stepX = width / (values.length - 1);
    const pts = values.map((v, i) => {
      const x = i * stepX;
      const y = height - ((v - min) / span) * height;
      return [x, y] as const;
    });
    const tonal =
      values[values.length - 1] >= values[0]
        ? "var(--color-feedback-success)"
        : "var(--color-feedback-error)";
    const lineD = pts
      .map((p, i) => `${i === 0 ? "M" : "L"} ${p[0].toFixed(1)} ${p[1].toFixed(1)}`)
      .join(" ");
    const areaD =
      lineD +
      ` L ${pts[pts.length - 1][0].toFixed(1)} ${height} L 0 ${height} Z`;
    return { line: lineD, area: areaD, tone: tonal };
  }, [values, width, height]);

  if (values.length < 2) {
    return (
      <div
        className={className}
        data-testid="area-empty"
        style={{ width, height, display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <span aria-hidden="true">—</span>
      </div>
    );
  }

  return (
    <svg
      role="img"
      aria-label="Price chart"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      data-testid="area-chart"
    >
      <defs>
        <linearGradient id={`g-${gid}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={tone} stopOpacity={0.32} />
          <stop offset="100%" stopColor={tone} stopOpacity={0} />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#g-${gid})`} stroke="none" />
      <path
        d={line}
        stroke={tone}
        strokeWidth={1.5}
        fill="none"
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
