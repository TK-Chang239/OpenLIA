import type { CSSProperties, JSX } from "react";

interface SkeletonProps {
  /** Width — number (px) or any CSS length. Defaults to full width. */
  width?: number | string;
  /** Height — number (px) or any CSS length. */
  height?: number | string;
  /** Border radius override (e.g. "9999px" for a pill, "50%" for a dot). */
  radius?: number | string;
  className?: string;
  style?: CSSProperties;
}

const toLen = (v: number | string | undefined): string | undefined =>
  typeof v === "number" ? `${v}px` : v;

/**
 * Shared loading skeleton block with the app's moving-gradient shimmer.
 * Replaces the old mix of flat `animate-pulse` blocks so every department's
 * loading state shares one consistent texture. Respects prefers-reduced-motion
 * via the `.ol-skeleton` rule in global.css.
 */
export function Skeleton({
  width,
  height = 12,
  radius,
  className,
  style,
}: SkeletonProps): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-testid="skeleton"
      className={["ol-skeleton block", className ?? ""].join(" ")}
      style={{
        width: toLen(width) ?? "100%",
        height: toLen(height),
        borderRadius: toLen(radius),
        ...style,
      }}
    />
  );
}
