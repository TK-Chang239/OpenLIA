import { Trash2 } from "lucide-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";

import type { PortfolioHolding, PositionAnalytic } from "../api/portfolio";
import { AreaChart } from "./AreaChart";
import { ALL_GROUP } from "./GroupTabs";

export interface HoldingsGridProps {
  readonly holdings: readonly PortfolioHolding[];
  readonly analyticsByHolding: ReadonlyMap<string, PositionAnalytic | undefined>;
  readonly activeGroup: string;
  readonly onRemove: (id: string) => void;
}

const fmt = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

function Card({
  h,
  a,
  onRemove,
  onClick,
}: {
  readonly h: PortfolioHolding;
  readonly a: PositionAnalytic | undefined;
  readonly onRemove: (id: string) => void;
  readonly onClick: () => void;
}): JSX.Element {
  const series = a?.last_price
    ? [Number(a.last_price) * 0.97, Number(a.last_price) * 0.99, Number(a.last_price), Number(a.last_price) * 1.01]
    : [];
  return (
    <article
      className="group relative min-w-[160px] rounded-[--radius-md] border border-[--color-border-subtle] p-3 cursor-pointer hover:bg-[--color-surface-hover]"
      onClick={onClick}
      data-testid={`holding-card-${h.ticker}`}
    >
      <header className="flex items-center justify-between mb-1">
        <div className="font-medium text-sm">{h.ticker}</div>
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(h.id);
          }}
          aria-label={`Remove ${h.ticker}`}
          className="opacity-0 group-hover:opacity-100 transition-opacity text-[--color-feedback-error]"
          data-testid={`grid-remove-${h.ticker}`}
        >
          <Trash2 size={14} aria-hidden="true" />
        </button>
      </header>
      <div className="text-xs text-[--color-text-tertiary] truncate mb-2">
        {h.name ?? ""}
      </div>
      <AreaChart values={series} width={220} height={100} />
      <footer className="mt-2 flex items-center justify-between text-sm tabular-nums">
        <span className="text-[--color-text-tertiary]">Last</span>
        <span className="font-medium">{fmt(a?.last_price ?? null)}</span>
      </footer>
    </article>
  );
}

export function HoldingsGrid({
  holdings,
  analyticsByHolding,
  activeGroup,
  onRemove,
}: HoldingsGridProps): JSX.Element {
  const navigate = useNavigate();

  // Sectioned grouping when "All" is active.
  const sections = useMemo(() => {
    if (activeGroup !== ALL_GROUP) {
      return [{ label: null as string | null, items: [...holdings] }];
    }
    const map = new Map<string, PortfolioHolding[]>();
    const ungrouped: PortfolioHolding[] = [];
    holdings.forEach((h) => {
      if (h.groups.length === 0) {
        ungrouped.push(h);
        return;
      }
      h.groups.forEach((g) => {
        const arr = map.get(g) ?? [];
        arr.push(h);
        map.set(g, arr);
      });
    });
    const out: { label: string | null; items: PortfolioHolding[] }[] = [];
    Array.from(map.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .forEach(([label, items]) => out.push({ label, items }));
    if (ungrouped.length) out.push({ label: "Ungrouped", items: ungrouped });
    if (out.length === 0) out.push({ label: null, items: [...holdings] });
    return out;
  }, [holdings, activeGroup]);

  return (
    <div data-testid="holdings-grid">
      {sections.map((section, idx) => (
        <section key={section.label ?? `s-${idx}`} className="mb-5">
          {section.label ? (
            <header className="flex items-center justify-between mb-2 border-b border-[--color-border-subtle] pb-1">
              <h3 className="text-xs font-medium text-[--color-text-tertiary]">
                {section.label} <span className="text-[--color-text-tertiary]">({section.items.length})</span>
              </h3>
            </header>
          ) : null}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {section.items.map((h) => (
              <Card
                key={h.id}
                h={h}
                a={analyticsByHolding.get(h.id)}
                onRemove={onRemove}
                onClick={() => navigate(`/equity-research?ticker=${h.ticker}`)}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
