import type { ReliabilityTier } from "../../lib/retail-sentiment/metric-catalog";
import { ReliabilityBadge } from "./ReliabilityBadge";

interface Props {
  label: string;
  value: number | string | null;
  units?: string;
  digits?: number;
  reliability?: ReliabilityTier;
  emphasis?: boolean;
  tooltip?: string;
  /** Sub-line shown below the value, e.g. "vs 30d avg" or a delta. */
  caption?: string;
  /** Optional inline visual (mini chart, bar, etc.) rendered below the value. */
  visual?: React.ReactNode;
  /** Disabled / cold-start state — gray out and append a hint. */
  disabledNote?: string;
}

function format(value: number | string | null, digits = 2): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  return Number.isFinite(value) ? value.toFixed(digits) : "—";
}

export function MetricCard({
  label,
  value,
  units,
  digits,
  reliability,
  emphasis,
  tooltip,
  caption,
  visual,
  disabledNote,
}: Props) {
  const disabled = Boolean(disabledNote);
  return (
    <div
      title={tooltip}
      className={[
        "rs-col-card",
        "p-4 flex flex-col gap-2 min-w-0",
        disabled ? "opacity-60" : "",
        emphasis ? "" : "",
      ].join(" ")}
      style={{ borderRadius: "10px" }}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="rs-mono-label truncate">{label}</span>
        {reliability ? <ReliabilityBadge tier={reliability} /> : null}
      </div>

      <div className="flex items-baseline gap-1.5">
        <span
          className={[
            "rs-mono-value",
            emphasis ? "text-[28px]" : "text-[20px]",
            "font-medium leading-none",
          ].join(" ")}
        >
          {format(value, digits)}
        </span>
        {units && value !== null && value !== undefined ? (
          <span
            className="rs-mono-label"
            style={{ letterSpacing: "0.04em" }}
          >
            {units}
          </span>
        ) : null}
      </div>

      {visual ? <div className="mt-1">{visual}</div> : null}

      {caption ? (
        <div
          className="rs-mono-label"
          style={{ letterSpacing: "0.06em", color: "var(--color-text-tertiary)" }}
        >
          {caption}
        </div>
      ) : null}

      {disabledNote ? (
        <div className="text-[11px] text-[--color-text-tertiary]">
          {disabledNote}
        </div>
      ) : null}
    </div>
  );
}
