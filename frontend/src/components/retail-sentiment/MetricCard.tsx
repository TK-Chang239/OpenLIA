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
}: Props) {
  return (
    <div
      title={tooltip}
      className={[
        "rounded-md border border-[--color-border-subtle] p-3",
        emphasis
          ? "bg-[--color-bg-elevated]"
          : "bg-[--color-bg-input]",
      ].join(" ")}
    >
      <div className="flex items-center justify-between text-[11px] uppercase tracking-wide text-[--color-text-secondary]">
        <span>{label}</span>
        {reliability ? <ReliabilityBadge tier={reliability} /> : null}
      </div>
      <div
        className={[
          "mt-1 font-semibold text-[--color-text-primary]",
          emphasis ? "text-2xl" : "text-lg",
        ].join(" ")}
      >
        {format(value, digits)}
        {units && value !== null ? (
          <span className="ml-1 text-xs text-[--color-text-secondary]">
            {units}
          </span>
        ) : null}
      </div>
    </div>
  );
}
