import type { JSX } from "react";

export interface DataRowProps {
  label: string;
  value: string;
  delta?: string;
  deltaDirection?: "pos" | "neg" | null;
}

export function DataRow({
  label,
  value,
  delta,
  deltaDirection,
}: DataRowProps): JSX.Element {
  return (
    <>
      <span className="ol-label">{label}</span>
      <span className="text-right font-mono text-[12px] font-medium tabular-nums text-text-primary">
        {value}
      </span>
      {delta ? (
        <span
          className="text-right font-mono text-[12px] tabular-nums"
          style={{
            color:
              deltaDirection === "neg"
                ? "var(--color-feedback-error)"
                : "var(--color-feedback-success)",
          }}
        >
          {delta}
        </span>
      ) : (
        <span />
      )}
    </>
  );
}
