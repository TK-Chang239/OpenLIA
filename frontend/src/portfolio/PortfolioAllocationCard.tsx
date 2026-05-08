import type { JSX } from "react";
import {
  computeAllocation,
  UNTAGGED,
  type AllocationRow,
} from "./allocation";
import type {
  AnalyticsResponse,
  PortfolioHolding,
} from "../api/portfolio";

export interface PortfolioAllocationCardProps {
  readonly holdings: readonly PortfolioHolding[];
  readonly analytics: AnalyticsResponse | null;
}

export function PortfolioAllocationCard({
  holdings,
  analytics,
}: PortfolioAllocationCardProps): JSX.Element {
  const rows = computeAllocation(holdings, analytics);
  const groupCount = rows.filter((r) => r.group !== UNTAGGED).length;

  return (
    <section
      aria-label="Portfolio allocation"
      className="rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[18px] py-[14px]"
      data-testid="portfolio-allocation-card"
    >
      <div className="mb-[10px] flex items-center justify-between font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        <span className="text-[--color-text-primary]">Portfolio allocation</span>
        <span>{groupCount} GROUPS</span>
      </div>

      {rows.length === 0 ? (
        <p className="py-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          Add a position to see allocation
        </p>
      ) : (
        <div className="flex flex-col">
          {rows.map((r) => (
            <AllocationRowView key={r.group} row={r} />
          ))}
        </div>
      )}
    </section>
  );
}

function AllocationRowView({ row }: { row: AllocationRow }): JSX.Element {
  const isUntagged = row.group === UNTAGGED;
  const widthPct = Math.max(0.5, Math.min(100, row.pct));
  return (
    <div
      className="grid grid-cols-[96px_1fr_50px] items-center gap-[10px] py-[7px]"
      data-testid={`allocation-row-${row.group}`}
    >
      <span
        className={`truncate text-[12px] ${isUntagged ? "text-[--color-text-tertiary] italic" : "text-[--color-text-primary]"}`}
        title={row.group}
      >
        {row.group}
      </span>
      <span className="relative h-[6px] overflow-hidden rounded-[3px] bg-[--color-bg-base]">
        <span
          className={`block h-full rounded-[3px] ${isUntagged ? "bg-[--color-text-tertiary] opacity-60" : "bg-[--color-accent-primary]"}`}
          style={{ width: `${widthPct}%` }}
        />
      </span>
      <span className="text-right font-mono text-[11px] tabular-nums text-[--color-text-secondary]">
        {row.pct.toFixed(1)}
      </span>
    </div>
  );
}
