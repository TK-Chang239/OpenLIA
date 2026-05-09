import type { JSX } from "react";
import { sparkFor, sparkPath } from "./sparkline";
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

export function KpiBand({ analytics, loading }: KpiBandProps): JSX.Element {
  if (loading) return <KpiBandSkeleton />;

  const totalMv = analytics ? Number(analytics.total_market_value) : 0;
  const navParts = fmtUsdAbbrev(totalMv);

  // Day P/L is a placeholder — see PORTFOLIO_DAY_PL_API in portfolio-remake.md
  const placeholderDayPl = totalMv * 0.0085;
  const dayParts = fmtUsdAbbrev(placeholderDayPl);

  return (
    <div
      className="grid grid-cols-1 overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] sm:grid-cols-2 lg:grid-cols-4"
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
          totalMv > 0 ? (
            <span className="text-[--color-feedback-success]">
              +${dayParts.whole}
              {dayParts.cents ? dayParts.cents : ""} today · +0.85%
            </span>
          ) : (
            <span className="text-[--color-text-tertiary]">—</span>
          )
        }
        sparkTicker="NAV"
        sparkSign="up"
      />
      <KpiCell
        label="Day P/L"
        value={
          totalMv > 0 ? (
            <>
              +{dayParts.whole}
              {dayParts.cents ? <small>{dayParts.cents}</small> : null}
            </>
          ) : (
            <>—</>
          )
        }
        delta={
          totalMv > 0 ? (
            <span className="text-[--color-feedback-success]">
              +0.85% · vs SPX +0.34%
            </span>
          ) : (
            <span className="text-[--color-text-tertiary]">placeholder</span>
          )
        }
        sparkTicker="DAY"
        sparkSign="up"
      />
      <KpiCell
        label="MTD"
        value={
          <>
            +4.21<small>%</small>
          </>
        }
        delta={
          <span className="text-[--color-feedback-success]">
            +$87,420 · alpha +120bp
          </span>
        }
        sparkTicker="MTD"
        sparkSign="up"
        placeholder
      />
      <KpiCell
        label="YTD"
        value={
          <>
            +22.8<small>%</small>
          </>
        }
        delta={
          <span className="text-[--color-feedback-success]">
            vs SPX +18.4% · sharpe 1.42
          </span>
        }
        sparkTicker="YTD"
        sparkSign="up"
        placeholder
      />
    </div>
  );
}

function KpiCell({
  label,
  value,
  delta,
  sparkTicker,
  sparkSign,
  placeholder = false,
}: {
  label: string;
  value: React.ReactNode;
  delta: React.ReactNode;
  sparkTicker: string;
  sparkSign: "up" | "flat" | "down";
  placeholder?: boolean;
}): JSX.Element {
  const spark = sparkFor(sparkTicker);
  const path = sparkPath(spark.points, 80);
  const stroke =
    sparkSign === "down"
      ? "var(--color-feedback-error)"
      : sparkSign === "flat"
        ? "var(--color-text-tertiary)"
        : "var(--yellow-600)";
  return (
    <div className="relative flex flex-col gap-2 border-b border-r border-[--color-border-subtle] px-5 py-[18px] last:border-r-0 sm:[&:nth-child(2)]:border-r-0 lg:[&:nth-child(2)]:border-r lg:[&:nth-child(4)]:border-r-0">
      <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
        {label}
        {placeholder ? (
          <span
            className="ml-2 rounded bg-[--color-surface-hover] px-1 py-px text-[8px] tracking-[0.1em]"
            title="Placeholder until backend ships"
          >
            STUB
          </span>
        ) : null}
      </span>
      <span className="font-mono text-[26px] font-medium leading-none tracking-[-0.01em] text-[--color-text-primary] tabular-nums">
        {value}
      </span>
      <span className="font-mono text-[11px] tabular-nums">{delta}</span>
      <svg
        viewBox="0 0 80 22"
        preserveAspectRatio="none"
        className="absolute right-4 top-4 h-[28px] w-[80px] opacity-70"
        aria-hidden="true"
      >
        <path d={path} fill="none" style={{ stroke }} strokeWidth="1.4" />
      </svg>
    </div>
  );
}

function KpiBandSkeleton(): JSX.Element {
  return (
    <div className="grid grid-cols-1 overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] sm:grid-cols-2 lg:grid-cols-4">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className="flex flex-col gap-2 border-b border-r border-[--color-border-subtle] px-5 py-[18px] last:border-r-0 lg:last:border-r-0"
        >
          <span className="h-[10px] w-16 animate-pulse rounded bg-[--color-border-subtle]" />
          <span className="h-[28px] w-32 animate-pulse rounded bg-[--color-border-subtle]" />
          <span className="h-[12px] w-40 animate-pulse rounded bg-[--color-border-subtle]" />
        </div>
      ))}
    </div>
  );
}
