import type { AnalyticsResponse } from "../api/portfolio";

export interface AnalyticsCardsProps {
  readonly analytics: AnalyticsResponse | null;
}

const fmt = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

const fmtPct = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return "";
  return `(${(n * 100).toFixed(2)}%)`;
};

function plClass(v: string | null | undefined): string {
  if (v === null || v === undefined) return "text-[--color-text-primary]";
  const n = Number(v);
  if (!Number.isFinite(n) || n === 0) return "text-[--color-text-primary]";
  return n > 0
    ? "text-[--color-feedback-success]"
    : "text-[--color-feedback-error]";
}

function AllocationChart({ allocations }: { readonly allocations: Record<string, string> }): JSX.Element | null {
  const entries = Object.entries(allocations).sort((a, b) => Number(b[1]) - Number(a[1]));
  if (entries.length === 0) return null;
  return (
    <div data-testid="allocation-chart" className="space-y-1">
      {entries.slice(0, 8).map(([ticker, weight]) => {
        const pct = Math.max(0, Math.min(1, Number(weight))) * 100;
        return (
          <div key={ticker} className="flex items-center gap-2 text-xs">
            <span className="font-mono w-12">{ticker}</span>
            <div className="flex-1 h-2 bg-[--color-border-subtle] rounded">
              <div
                className="h-full bg-[--color-accent-primary] rounded"
                style={{ width: `${pct.toFixed(1)}%` }}
              />
            </div>
            <span className="tabular-nums w-12 text-right text-[--color-text-tertiary]">
              {pct.toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function AnalyticsCards({ analytics }: AnalyticsCardsProps): JSX.Element {
  return (
    <section className="space-y-4" data-testid="analytics-cards">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
          <div className="text-xs text-[--color-text-tertiary]">Market Value</div>
          <div className="text-xl font-semibold tabular-nums">
            {fmt(analytics?.total_market_value)}
          </div>
        </div>
        <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
          <div className="text-xs text-[--color-text-tertiary]">Cost Basis</div>
          <div className="text-xl font-semibold tabular-nums">
            {fmt(analytics?.total_cost_basis)}
          </div>
        </div>
        <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
          <div className="text-xs text-[--color-text-tertiary]">Unrealized P/L</div>
          <div
            className={`text-xl font-semibold tabular-nums ${plClass(analytics?.total_unrealized_pl)}`}
            data-testid="pl-value"
          >
            {fmt(analytics?.total_unrealized_pl)}{" "}
            <span className="text-sm">{fmtPct(analytics?.total_unrealized_pl_pct)}</span>
          </div>
        </div>
      </div>
      {analytics?.allocations ? (
        <div className="p-4 rounded-[--radius-md] border border-[--color-border-subtle]">
          <div className="text-xs text-[--color-text-tertiary] mb-2">Allocation</div>
          <AllocationChart allocations={analytics.allocations} />
        </div>
      ) : null}
    </section>
  );
}
