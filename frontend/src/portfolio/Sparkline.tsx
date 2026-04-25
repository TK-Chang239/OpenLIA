import { useMemo } from "react";

export interface SparklineProps {
  readonly values: readonly number[];
  readonly width?: number;
  readonly height?: number;
  readonly className?: string;
  /** Optional override for the line/fill color. Defaults to up/down semantic. */
  readonly color?: string;
}

/**
 * Sparkline — inline SVG line chart. ~80x28 by spec.
 * Color derives from sign of the last delta (green up / red down).
 */
export function Sparkline({
  values,
  width = 80,
  height = 28,
  className,
  color,
}: SparklineProps): JSX.Element {
  const points = useMemo(() => {
    if (values.length < 2) return null;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const stepX = width / (values.length - 1);
    return values
      .map((v, i) => {
        const x = i * stepX;
        const y = height - ((v - min) / span) * height;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [values, width, height]);

  if (!values || values.length < 2) {
    return (
      <span
        className={className}
        data-testid="sparkline-empty"
        aria-hidden="true"
        style={{ width, height, display: "inline-block", textAlign: "center" }}
      >
        —
      </span>
    );
  }

  const last = values[values.length - 1];
  const first = values[0];
  const tone =
    color ??
    (last >= first
      ? "var(--color-feedback-success)"
      : "var(--color-feedback-error)");

  return (
    <svg
      role="img"
      aria-label="Sparkline"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={className}
      data-testid="sparkline"
    >
      <polyline
        fill="none"
        stroke={tone}
        strokeWidth={1.4}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points ?? ""}
      />
    </svg>
  );
}
