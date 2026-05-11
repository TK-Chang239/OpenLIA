import { useEffect } from "react";
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { Edit3, ExternalLink, Trash2, X } from "lucide-react";
import type {
  AnalyticsResponse,
  PortfolioHolding,
  PositionAnalytic,
} from "../api/portfolio";

export interface HoldingDetailDrawerProps {
  readonly open: boolean;
  readonly holding: PortfolioHolding | null;
  readonly analytics: AnalyticsResponse | null;
  readonly onClose: () => void;
  readonly onEdit: (holding: PortfolioHolding) => void;
  readonly onRemove: (holding: PortfolioHolding) => void;
}

export function HoldingDetailDrawer({
  open,
  holding,
  analytics,
  onClose,
  onEdit,
  onRemove,
}: HoldingDetailDrawerProps): JSX.Element | null {
  const navigate = useNavigate();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !holding) return null;

  const position =
    analytics?.positions.find((p) => p.holding_id === holding.id) ?? null;

  return (
    <div className="fixed inset-0 z-30" data-testid="holding-detail-drawer">
      <button
        type="button"
        aria-label="Close drawer"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-black/30 backdrop-blur-[2px]"
      />
      <aside
        role="dialog"
        aria-label={`${holding.ticker} details`}
        className="absolute right-0 top-0 flex h-full w-full max-w-[480px] flex-col bg-[--color-bg-base] shadow-[-12px_0_40px_rgba(0,0,0,0.16)] motion-safe:animate-[ol-drawer-in_240ms_ease-out]"
      >
        <DrawerHeader
          holding={holding}
          position={position}
          onClose={onClose}
          onOpenEquityResearch={() =>
            navigate(`/equity-research?ticker=${encodeURIComponent(holding.ticker)}`)
          }
        />
        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="flex flex-col gap-5">
            <PositionSummary position={position} />
            <MiniChart />
            <RecentActivity />
            <RelatedReports ticker={holding.ticker} />
            <LiaTake
              ticker={holding.ticker}
              onAskLia={() =>
                navigate(
                  `/secretary?prompt=${encodeURIComponent(`Tell me about ${holding.ticker}.`)}`,
                )
              }
              onOpenEquityResearch={() =>
                navigate(`/equity-research?ticker=${encodeURIComponent(holding.ticker)}`)
              }
            />
          </div>
        </div>
        <DrawerFooter
          onEdit={() => onEdit(holding)}
          onRemove={() => onRemove(holding)}
        />
      </aside>
    </div>
  );
}

function DrawerHeader({
  holding,
  position,
  onClose,
  onOpenEquityResearch,
}: {
  holding: PortfolioHolding;
  position: PositionAnalytic | null;
  onClose: () => void;
  onOpenEquityResearch: () => void;
}): JSX.Element {
  const price = position?.last_price ? `$${Number(position.last_price).toFixed(2)}` : "—";
  return (
    <header className="border-b border-[--color-border-subtle] px-5 py-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <span className="inline-flex items-center gap-2">
            <span className="rounded bg-[--color-bg-code] px-[6px] py-[2px] font-mono text-[12px] font-semibold tracking-[0.02em] text-[--color-text-primary]">
              {holding.ticker}
            </span>
            <span className="font-display text-[15px] font-medium text-[--color-text-primary]">
              {holding.name ?? "—"}
            </span>
          </span>
          <span className="font-mono text-[12px] tabular-nums text-[--color-text-secondary]">
            {price}
            {holding.groups[0] ? (
              <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                · {holding.groups[0]}
              </span>
            ) : null}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onOpenEquityResearch}
            className="inline-flex items-center gap-1 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-2 py-1 font-mono text-[10px] tracking-[0.06em] text-[--color-text-secondary] transition-colors hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
            data-testid="drawer-open-er"
          >
            <ExternalLink size={11} aria-hidden="true" />
            Equity Research
          </button>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="inline-flex h-7 w-7 items-center justify-center rounded text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            data-testid="drawer-close"
          >
            <X size={14} aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>
  );
}

function PositionSummary({ position }: { position: PositionAnalytic | null }): JSX.Element {
  const cells: { label: string; value: string }[] = [
    {
      label: "Shares",
      value: position?.shares ? Number(position.shares).toLocaleString() : "—",
    },
    {
      label: "Avg cost",
      value: position?.cost_basis ? `$${Number(position.cost_basis).toFixed(2)}` : "—",
    },
    {
      label: "Market value",
      value: position?.market_value
        ? `$${Number(position.market_value).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
        : "—",
    },
    {
      label: "Unrealized P/L",
      value: position?.unrealized_pl
        ? `${Number(position.unrealized_pl) >= 0 ? "+" : "-"}$${Math.abs(Number(position.unrealized_pl)).toLocaleString("en-US", { maximumFractionDigits: 0 })}`
        : "—",
    },
    {
      label: "Unrealized P/L %",
      value: position?.unrealized_pl_pct
        ? `${Number(position.unrealized_pl_pct) >= 0 ? "+" : ""}${(Number(position.unrealized_pl_pct) * 100).toFixed(2)}%`
        : "—",
    },
    {
      label: "Weight",
      value: position?.weight ? `${(Number(position.weight) * 100).toFixed(1)}%` : "—",
    },
  ];
  return (
    <Section title="Position">
      <div className="grid grid-cols-3 gap-2">
        {cells.map((c) => (
          <div
            key={c.label}
            className="flex flex-col gap-1 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-3"
          >
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {c.label}
            </span>
            <span className="font-mono text-[14px] tabular-nums text-[--color-text-primary]">
              {c.value}
            </span>
          </div>
        ))}
      </div>
    </Section>
  );
}

function MiniChart(): JSX.Element {
  return (
    <Section title="Performance" subtitle="Per-holding timeseries pending">
      <div className="flex h-[120px] items-center justify-center rounded-md border border-dashed border-[--color-border-subtle] bg-[--color-bg-elevated] p-3 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
        No data
      </div>
    </Section>
  );
}

function RecentActivity(): JSX.Element {
  return (
    <Section title="Recent activity" subtitle="Trade log pending">
      <p className="rounded-md border border-dashed border-[--color-border-subtle] p-3 text-center text-[12px] text-[--color-text-tertiary]">
        No trade history yet.
      </p>
    </Section>
  );
}

function RelatedReports({ ticker }: { ticker: string }): JSX.Element {
  return (
    <Section title="Related reports">
      <p className="rounded-md border border-dashed border-[--color-border-subtle] p-3 text-center text-[12px] text-[--color-text-tertiary]">
        No reports mention {ticker} yet.
      </p>
    </Section>
  );
}

function LiaTake({
  ticker,
  onAskLia,
  onOpenEquityResearch,
}: {
  ticker: string;
  onAskLia: () => void;
  onOpenEquityResearch: () => void;
}): JSX.Element {
  return (
    <Section title="LIA take" subtitle="Per-holding verdicts pending">
      <div className="flex gap-3 rounded-md border-l-2 border-[--color-accent-primary] bg-[rgba(212,255,0,0.04)] px-4 py-3">
        <span className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-[--color-accent-primary] font-mono text-[10px] font-bold text-[--color-accent-on] shadow-[0_0_8px_rgba(212,255,0,0.35)]">
          LIA
        </span>
        <div className="flex flex-1 flex-col gap-2">
          <p className="m-0 text-[13px] leading-[1.5] text-[--color-text-tertiary]">
            No verdict yet for {ticker}.
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onOpenEquityResearch}
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1 font-mono text-[10px] tracking-[0.06em] text-[--color-text-primary] transition-colors hover:border-[--color-border-strong]"
            >
              Open Equity Research
            </button>
            <button
              type="button"
              onClick={onAskLia}
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-1 font-mono text-[10px] tracking-[0.06em] text-[--color-text-primary] transition-colors hover:border-[--color-border-strong]"
            >
              Ask LIA about {ticker}
            </button>
          </div>
        </div>
      </div>
    </Section>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section className="flex flex-col gap-2">
      <header className="flex items-baseline justify-between gap-3">
        <h3 className="m-0 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-[--color-text-primary]">
          {title}
        </h3>
        {subtitle ? (
          <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
            {subtitle}
          </span>
        ) : null}
      </header>
      {children}
    </section>
  );
}

function DrawerFooter({
  onEdit,
  onRemove,
}: {
  onEdit: () => void;
  onRemove: () => void;
}): JSX.Element {
  return (
    <footer className="flex items-center justify-between gap-3 border-t border-[--color-border-subtle] bg-[--color-bg-elevated] px-5 py-3">
      <button
        type="button"
        onClick={onEdit}
        className="inline-flex items-center gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] text-[--color-text-primary] transition-colors hover:border-[--color-border-strong]"
        data-testid="drawer-edit"
      >
        <Edit3 size={11} aria-hidden="true" />
        EDIT POSITION
      </button>
      <button
        type="button"
        onClick={onRemove}
        className="inline-flex items-center gap-2 rounded-md border border-[--color-feedback-error] bg-transparent px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] text-[--color-feedback-error] transition-colors hover:bg-[rgba(224,92,48,0.1)]"
        data-testid="drawer-remove"
      >
        <Trash2 size={11} aria-hidden="true" />
        REMOVE
      </button>
    </footer>
  );
}
