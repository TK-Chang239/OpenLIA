import { useEffect, useId, useState } from "react";
import type { JSX } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Edit3, ExternalLink, Trash2, X } from "lucide-react";
import type {
  AnalyticsResponse,
  PortfolioHolding,
  PositionAnalytic,
} from "../api/portfolio";
import { PERF_PATHS, PERF_TABS, type PerfTab } from "./perfPaths";

export interface HoldingDetailDrawerProps {
  readonly open: boolean;
  readonly holding: PortfolioHolding | null;
  readonly analytics: AnalyticsResponse | null;
  readonly onClose: () => void;
  readonly onEdit: (holding: PortfolioHolding) => void;
  readonly onRemove: (holding: PortfolioHolding) => void;
}

interface PlaceholderReport {
  id: string;
  department: "equity_research" | "earnings_update" | "morning_briefing";
  title: string;
  generatedAt: string; // ISO
}

const DEPT_LABEL: Record<PlaceholderReport["department"], string> = {
  equity_research: "Equity Research",
  earnings_update: "Earnings Update",
  morning_briefing: "Morning Briefing",
};

const DEPT_DOT_CLASS: Record<PlaceholderReport["department"], string> = {
  equity_research: "bg-[--color-accent-primary]",
  earnings_update: "bg-[--color-feedback-warning]",
  morning_briefing: "bg-[--color-feedback-success]",
};

function placeholderReports(ticker: string): PlaceholderReport[] {
  // Three deterministic placeholder rows so the drawer feels alive.
  // Replace with `listRepoItemsFiltered({ q: ticker, departments: [...], sort: "generated_desc", page_size: 6 })`
  // once REPO_BODY_FULLTEXT_SEARCH ships.
  return [
    {
      id: `placeholder-er-${ticker}`,
      department: "equity_research",
      title: `${ticker} — Q1 FY27 deep-dive`,
      generatedAt: "2026-05-02T15:20:00Z",
    },
    {
      id: `placeholder-eu-${ticker}`,
      department: "earnings_update",
      title: `${ticker} earnings recap · post-call`,
      generatedAt: "2026-04-28T22:18:00Z",
    },
    {
      id: `placeholder-mb-${ticker}`,
      department: "morning_briefing",
      title: `Morning briefing · 2026-04-25 · ${ticker} flagged`,
      generatedAt: "2026-04-25T13:05:00Z",
    },
  ];
}

function relativeTime(iso: string, now: Date = new Date()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "—";
  const diff = (now.getTime() - t) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 7 * 86400) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(t).toISOString().slice(0, 10);
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
            <RecentActivity ticker={holding.ticker} />
            <RelatedReports
              ticker={holding.ticker}
              reports={placeholderReports(holding.ticker)}
              onOpen={(reportId) =>
                navigate(`/repository?open=${encodeURIComponent(reportId)}`)
              }
            />
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
  const [tab, setTab] = useState<PerfTab>("NAV");
  const p = PERF_PATHS[tab];
  const gradId = useId();
  return (
    <Section
      title="Performance"
      subtitle="Placeholder · per-holding timeseries pending"
    >
      <div className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-3">
        <div className="mb-2 flex items-center gap-3">
          {PERF_TABS.map((t) => (
            <button
              key={t}
              type="button"
              onClick={() => setTab(t)}
              className={`cursor-pointer border-b pb-1 font-mono text-[9px] tracking-[0.08em] transition-colors ${tab === t ? "border-[--color-accent-primary] text-[--color-text-primary]" : "border-transparent text-[--color-text-tertiary] hover:text-[--color-text-secondary]"}`}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="h-[120px]">
          <svg viewBox="0 0 800 110" preserveAspectRatio="none" className="h-full w-full">
            <defs>
              <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0.32 }} />
                <stop offset="100%" style={{ stopColor: "var(--color-accent-primary)", stopOpacity: 0 }} />
              </linearGradient>
            </defs>
            <path d={p.area} fill={`url(#${gradId})`} />
            <path d={p.line} fill="none" style={{ stroke: "var(--yellow-600)" }} strokeWidth="1.6" />
          </svg>
        </div>
      </div>
    </Section>
  );
}

function RecentActivity({ ticker }: { ticker: string }): JSX.Element {
  const rows = [
    { date: "2025-11-20", action: "ADDED", text: `100 sh @ $128.40` },
    { date: "2025-08-12", action: "ADDED", text: `50 sh @ $115.10` },
    { date: "2025-04-04", action: "ADDED", text: `25 sh @ $98.55` },
  ];
  return (
    <Section title="Recent activity" subtitle="Placeholder · trade log pending">
      <ul className="flex flex-col">
        {rows.map((r, i) => (
          <li
            key={i}
            className={`flex items-center gap-3 py-2 font-mono text-[12px] tabular-nums ${i < rows.length - 1 ? "border-b border-dashed border-[--color-border-subtle]" : ""}`}
          >
            <span className="w-[90px] text-[--color-text-tertiary]">{r.date}</span>
            <span className="w-[60px] text-[--color-feedback-success]">{r.action}</span>
            <span className="flex-1 text-[--color-text-primary]">{r.text}</span>
          </li>
        ))}
      </ul>
      <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
        ticker · {ticker}
      </p>
    </Section>
  );
}

function RelatedReports({
  ticker,
  reports,
  onOpen,
}: {
  ticker: string;
  reports: PlaceholderReport[];
  onOpen: (reportId: string) => void;
}): JSX.Element {
  return (
    <Section
      title="Related reports"
      subtitle={`Placeholder · ${reports.length} mentioning ${ticker}`}
    >
      {reports.length === 0 ? (
        <p className="rounded-md border border-dashed border-[--color-border-subtle] p-3 text-center text-[12px] text-[--color-text-tertiary]">
          No reports mention {ticker} yet.
        </p>
      ) : (
        <ul className="flex flex-col">
          {reports.map((r, i) => (
            <li
              key={r.id}
              className={`group flex cursor-pointer items-center gap-3 rounded-md px-2 py-2 transition-colors hover:bg-[--color-surface-hover] ${i < reports.length - 1 ? "" : ""}`}
              onClick={() => onOpen(r.id)}
              data-testid={`related-report-${r.id}`}
            >
              <span
                aria-hidden="true"
                className={`h-2 w-2 flex-shrink-0 rounded-full ${DEPT_DOT_CLASS[r.department]}`}
              />
              <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="truncate text-[13px] text-[--color-text-primary]">
                  {r.title}
                </span>
                <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                  {DEPT_LABEL[r.department]} · {relativeTime(r.generatedAt)}
                </span>
              </div>
              <ArrowRight
                size={12}
                aria-hidden="true"
                className="text-[--color-text-tertiary] transition-colors group-hover:text-[--color-text-primary]"
              />
            </li>
          ))}
        </ul>
      )}
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
    <Section title="LIA take" subtitle="Placeholder · per-holding verdicts pending">
      <div className="flex gap-3 rounded-md border-l-2 border-[--color-accent-primary] bg-[rgba(212,255,0,0.04)] px-4 py-3">
        <span className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md bg-[--color-accent-primary] font-mono text-[10px] font-bold text-[--color-accent-on] shadow-[0_0_8px_rgba(212,255,0,0.35)]">
          LIA
        </span>
        <div className="flex flex-1 flex-col gap-2">
          <p className="m-0 text-[13px] leading-[1.5] text-[--color-text-primary]">
            {ticker} is contributing an estimated{" "}
            <strong>placeholder %</strong> of book variance over 30d. Verdict
            copy will land here when the per-holding judgement API ships.
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
