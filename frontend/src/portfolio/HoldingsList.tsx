import { Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import type {
  PortfolioHolding,
  PositionAnalytic,
} from "../api/portfolio";
import { Sparkline } from "./Sparkline";

export interface HoldingsListProps {
  readonly holdings: readonly PortfolioHolding[];
  readonly analyticsByHolding: ReadonlyMap<string, PositionAnalytic | undefined>;
  readonly onRemove: (id: string) => void;
}

const fmt = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
};

const fmtPct = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return `${(n * 100).toFixed(2)}%`;
};

function HoldingRow({
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
  const [pctMode, setPctMode] = useState(false);
  // Derive a placeholder sparkline series from current price so the SVG
  // renders something meaningful on real data; empty when no price.
  const series = a?.last_price
    ? [Number(a.last_price) * 0.97, Number(a.last_price), Number(a.last_price) * 1.01]
    : [];
  return (
    <li
      className="group relative flex items-center gap-3 px-3 h-[60px] border-b border-[--color-border-subtle] cursor-pointer hover:bg-[--color-surface-hover]"
      onClick={onClick}
      data-testid={`holding-row-${h.ticker}`}
    >
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm">{h.ticker}</div>
        {h.name ? (
          <div className="text-xs text-[--color-text-tertiary] truncate">
            {h.name}
          </div>
        ) : null}
      </div>
      <div className="hidden md:block">
        <Sparkline values={series} />
      </div>
      <div className="text-sm font-medium tabular-nums text-right w-24">
        {fmt(a?.last_price ?? null)}
      </div>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          setPctMode((p) => !p);
        }}
        className="text-xs px-2 py-0.5 rounded-[--radius-sm] border border-[--color-border-subtle] hover:bg-[--color-surface-hover] text-[--color-text-tertiary] tabular-nums"
        data-testid={`metric-badge-${h.ticker}`}
      >
        {pctMode ? fmtPct(a?.unrealized_pl_pct ?? null) : fmt(a?.unrealized_pl ?? null)}
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onRemove(h.id);
        }}
        aria-label={`Remove ${h.ticker}`}
        className="opacity-0 group-hover:opacity-100 transition-opacity text-[--color-feedback-error]"
        data-testid={`remove-${h.ticker}`}
      >
        <Trash2 size={14} aria-hidden="true" />
      </button>
    </li>
  );
}

export function HoldingsList({
  holdings,
  analyticsByHolding,
  onRemove,
}: HoldingsListProps): JSX.Element {
  const navigate = useNavigate();
  return (
    <ul className="rounded-[--radius-md] border border-[--color-border-subtle] overflow-hidden">
      {holdings.map((h) => (
        <HoldingRow
          key={h.id}
          h={h}
          a={analyticsByHolding.get(h.id)}
          onRemove={onRemove}
          onClick={() => navigate(`/equity-research?ticker=${h.ticker}`)}
        />
      ))}
    </ul>
  );
}
