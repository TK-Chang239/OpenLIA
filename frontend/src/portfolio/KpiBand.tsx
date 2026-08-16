import type { JSX } from "react";
import type { AnalyticsResponse } from "../api/portfolio";
import { formatCurrency } from "./formatCurrency";

export interface KpiBandProps {
  readonly analytics: AnalyticsResponse | null;
  readonly loading: boolean;
}

function fmtPct(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const sign = n >= 0 ? "+" : "";
  return `${sign}${(n * 100).toFixed(2)}%`;
}

interface CurrencySubtotal {
  currency: string;
  marketValue: number;
  unrealizedPl: number;
  plPct: number;
}

/** Segregate positions into per-currency subtotals. Values are never summed across
 *  currencies — the combined totals are meaningless without FX conversion. */
function perCurrencySubtotals(analytics: AnalyticsResponse): CurrencySubtotal[] {
  const acc = new Map<string, { mv: number; pl: number }>();
  for (const p of analytics.positions) {
    const mv = p.market_value === null ? 0 : Number(p.market_value);
    const pl = p.unrealized_pl === null ? 0 : Number(p.unrealized_pl);
    const cur = acc.get(p.currency) ?? { mv: 0, pl: 0 };
    if (Number.isFinite(mv)) cur.mv += mv;
    if (Number.isFinite(pl)) cur.pl += pl;
    acc.set(p.currency, cur);
  }
  return [...acc.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([currency, { mv, pl }]) => {
      const cost = mv - pl;
      return {
        currency,
        marketValue: mv,
        unrealizedPl: pl,
        plPct: cost !== 0 ? pl / cost : NaN,
      };
    });
}

export function KpiBand({ analytics, loading }: KpiBandProps): JSX.Element {
  if (loading) return <KpiBandSkeleton />;

  const mixed = (analytics?.currencies_present?.length ?? 0) > 1;
  if (analytics && mixed) return <MixedKpiBand analytics={analytics} />;

  const currency = analytics?.display_currency ?? "USD";
  const totalMv = analytics ? Number(analytics.total_market_value) : 0;
  const totalPl = analytics ? Number(analytics.total_unrealized_pl) : 0;
  const totalPlPct = analytics?.total_unrealized_pl_pct
    ? Number(analytics.total_unrealized_pl_pct)
    : NaN;
  const totalCost = analytics ? Number(analytics.total_cost_basis) : 0;
  const hasValue = Number.isFinite(totalMv) && totalMv > 0;
  const plPositive = totalPl >= 0;

  return (
    <div
      className="grid grid-cols-1 overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated] sm:grid-cols-2"
      data-testid="kpi-band"
    >
      <KpiCell
        label="Total NAV"
        value={formatCurrency(Number.isFinite(totalMv) ? totalMv : null, currency)}
        delta={
          <span className="text-[--color-text-tertiary]">
            cost {formatCurrency(Number.isFinite(totalCost) ? totalCost : null, currency)}
          </span>
        }
      />
      <KpiCell
        label="Unrealized P/L"
        value={
          hasValue ? (
            <span
              className={plPositive ? "text-[--color-feedback-success]" : "text-[--color-feedback-error]"}
            >
              {formatCurrency(totalPl, currency, { signed: true })}
            </span>
          ) : (
            <>—</>
          )
        }
        delta={
          hasValue ? (
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

/** Multi-currency view: one row per currency, never a combined (unconverted) total. */
function MixedKpiBand({ analytics }: { analytics: AnalyticsResponse }): JSX.Element {
  const rows = perCurrencySubtotals(analytics);
  return (
    <div
      className="overflow-hidden rounded-xl border border-[--color-border-subtle] bg-[--color-bg-elevated]"
      data-testid="kpi-band"
      data-mixed-currency="true"
    >
      <div className="flex items-center justify-between border-b border-[--color-border-subtle] px-5 pt-[14px] pb-2">
        <span className="font-mono text-[9px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
          Portfolio value
        </span>
        <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
          By currency · no FX
        </span>
      </div>
      <div className="flex flex-col">
        {rows.map((r) => {
          const positive = r.unrealizedPl >= 0;
          const plClass = positive
            ? "text-[--color-feedback-success]"
            : "text-[--color-feedback-error]";
          return (
            <div
              key={r.currency}
              className="grid grid-cols-[48px_1fr_auto] items-baseline gap-3 border-b border-[--color-border-subtle] px-5 py-3 last:border-b-0"
              data-testid={`kpi-currency-${r.currency}`}
            >
              <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                {r.currency}
              </span>
              <span className="font-mono text-[20px] font-medium leading-none tracking-[-0.01em] text-[--color-text-primary] tabular-nums">
                {formatCurrency(r.marketValue, r.currency)}
              </span>
              <span className={`text-right font-mono text-[11px] tabular-nums ${plClass}`}>
                {formatCurrency(r.unrealizedPl, r.currency, { signed: true })}{" "}
                <span className="text-[--color-text-tertiary]">({fmtPct(r.plPct)})</span>
              </span>
            </div>
          );
        })}
      </div>
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
          <span className="ol-skeleton inline-block h-[10px] w-16" />
          <span className="ol-skeleton inline-block h-[28px] w-32" />
          <span className="ol-skeleton inline-block h-[12px] w-40" />
        </div>
      ))}
    </div>
  );
}
