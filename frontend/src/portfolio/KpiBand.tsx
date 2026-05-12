import type { JSX } from "react";
import type { AnalyticsResponse } from "../api/portfolio";

export interface KpiBandProps {
  readonly analytics: AnalyticsResponse | null;
  readonly loading: boolean;
}

function fmtUsdAbbrev(n: number): { whole: string; cents: string } {
  if (!Number.isFinite(n)) return { whole: "—", cents: "" };
  const sign = n < 0 ? "-" : "";
  const abs = Math.abs(n);
  const whole = Math.floor(abs).toLocaleString("en-US");
  const cents = (abs - Math.floor(abs)).toFixed(2).slice(1);
  return { whole: `${sign}${whole}`, cents };
}

function fmtPct(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}%`;
}

export function KpiBand({ analytics, loading }: KpiBandProps): JSX.Element {
  if (loading) return <KpiBandSkeleton />;

  const totalMv = analytics ? Number(analytics.total_market_value) : 0;
  const totalPl = analytics ? Number(analytics.total_unrealized_pl) : 0;
  const totalPlPct = analytics?.total_unrealized_pl_pct ? Number(analytics.total_unrealized_pl_pct) : NaN;
  const totalCost = analytics ? Number(analytics.total_cost_basis) : 0;

  const navParts = fmtUsdAbbrev(totalMv);
  const plParts = fmtUsdAbbrev(totalPl);
  const costParts = fmtUsdAbbrev(totalCost);
  const plPositive = totalPl >= 0;

  return (
    <div
      className="grid grid-cols-1 overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] sm:grid-cols-2"
      data-testid="kpi-band"
    >
      <KpiCell
        label="Total NAV"
        value={
          <>
            ${navParts.whole}
            {navParts.cents ? <small>{navParts.cents}</small> : null}
          </>
        }
        delta={
          <span className="text-[--color-text-tertiary]">
            cost ${costParts.whole}
            {costParts.cents ? costParts.cents : ""}
          </span>
        }
      />
      <KpiCell
        label="Unrealized P/L"
        value={
          totalMv > 0 ? (
            <span
              className={plPositive ? "text-[--color-feedback-success]" : "text-[--color-feedback-error]"}
            >
              {plPositive ? "+" : "-"}${fmtUsdAbbrev(Math.abs(totalPl)).whole}
              {plParts.cents ? <small>{plParts.cents}</small> : null}
            </span>
          ) : (
            <>—</>
          )
        }
        delta={
          totalMv > 0 ? (
            <span
              className={plPositive ? "text-[--color-feedback-success]" : "text-[--color-feedback-error]"}
            >
              {fmtPct(totalPlPct)}
            </span>
          ) : (
            <span className="text-[--color-text-tertiary]">—</span>
          )
        }
      />
    </div>
  );
}

function KpiCell({
  label,
  value,
  delta,
}: {
  label: string;
  value: React.ReactNode;
  delta: React.ReactNode;
}): JSX.Element {
  return (
    <div className="relative flex flex-col gap-2 border-b border-r border-[--color-border-subtle] px-5 py-[18px] last:border-r-0 sm:[&:nth-child(2)]:border-r-0">
      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        {label}
      </span>
      <span className="font-mono text-[26px] font-medium leading-none tracking-[-0.01em] text-[--color-text-primary] tabular-nums">
        {value}
      </span>
      <span className="font-mono text-[11px] tabular-nums">{delta}</span>
    </div>
  );
}

function KpiBandSkeleton(): JSX.Element {
  return (
    <div className="grid grid-cols-1 overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] sm:grid-cols-2">
      {[0, 1].map((i) => (
        <div
          key={i}
          className="flex flex-col gap-2 border-b border-r border-[--color-border-subtle] px-5 py-[18px] last:border-r-0"
        >
          <span className="h-[10px] w-16 animate-pulse rounded bg-[--color-border-subtle]" />
          <span className="h-[28px] w-32 animate-pulse rounded bg-[--color-border-subtle]" />
          <span className="h-[12px] w-40 animate-pulse rounded bg-[--color-border-subtle]" />
        </div>
      ))}
    </div>
  );
}
