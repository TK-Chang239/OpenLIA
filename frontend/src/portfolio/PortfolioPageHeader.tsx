import { useEffect, useRef, useState } from "react";
import type { JSX } from "react";
import { ChevronDown, Download, Plus, RotateCw } from "lucide-react";

export const PERF_RANGES = ["1D", "1W", "1M", "YTD", "ALL"] as const;
export type PerfRange = (typeof PERF_RANGES)[number];

export interface PortfolioPageHeaderProps {
  readonly holdingCount: number;
  readonly lastSyncedAt: string | null;
  readonly refreshing: boolean;
  readonly onRefresh: () => void;
  readonly range: PerfRange;
  readonly onRangeChange: (next: PerfRange) => void;
  readonly exportHref: string;
  readonly onAddManually: () => void;
  readonly onImportCsv: () => void;
}

function formatSync(at: string | null): string {
  if (!at) return "—";
  const t = Date.parse(at);
  if (!Number.isFinite(t)) return "—";
  const d = new Date(t);
  const hh = String(d.getUTCHours()).padStart(2, "0");
  const mm = String(d.getUTCMinutes()).padStart(2, "0");
  return `${hh}:${mm} UTC`;
}

export function PortfolioPageHeader({
  holdingCount,
  lastSyncedAt,
  refreshing,
  onRefresh,
  range,
  onRangeChange,
  exportHref,
  onAddManually,
  onImportCsv,
}: PortfolioPageHeaderProps): JSX.Element {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div className="flex flex-col gap-[6px]">
        <span className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-[--color-text-tertiary]">
          <span aria-hidden="true" className="h-px w-[18px] bg-[--color-border-strong]" />
          PERSONAL · USD · LAST SYNCED {formatSync(lastSyncedAt)}
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            aria-label="Refresh prices"
            title="Refresh prices"
            className="ml-1 inline-flex h-5 w-5 items-center justify-center rounded text-[--color-text-tertiary] transition-colors hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:opacity-60"
            data-testid="refresh-prices"
          >
            <RotateCw size={11} aria-hidden="true" className={refreshing ? "animate-spin" : ""} />
          </button>
        </span>
        <h1 className="font-display m-0 text-[30px] font-medium leading-[1.1] tracking-[-0.02em] text-[--color-text-primary]">
          My Portfolio
          <small className="ml-[10px] font-mono text-[11px] font-normal uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            {holdingCount} HOLDINGS
          </small>
        </h1>
      </div>

      <div className="flex items-center gap-2">
        <RangePicker value={range} onChange={onRangeChange} />
        <a
          href={exportHref}
          className="inline-flex items-center gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] text-[--color-text-secondary] no-underline transition-colors hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
          data-testid="export-csv"
        >
          <Download size={11} aria-hidden="true" />
          EXPORT
        </a>
        <AddSplitButton onAddManually={onAddManually} onImportCsv={onImportCsv} />
      </div>
    </header>
  );
}

function RangePicker({
  value,
  onChange,
}: {
  value: PerfRange;
  onChange: (next: PerfRange) => void;
}): JSX.Element {
  return (
    <span
      role="tablist"
      aria-label="Perf chart range"
      className="inline-flex overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated]"
    >
      {PERF_RANGES.map((r) => (
        <button
          key={r}
          role="tab"
          aria-selected={value === r}
          type="button"
          onClick={() => onChange(r)}
          className={`border-r border-[--color-border-subtle] px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] last:border-r-0 ${
            value === r
              ? "bg-[--color-text-primary] text-[--color-bg-base]"
              : "text-[--color-text-secondary] hover:text-[--color-text-primary]"
          }`}
          data-testid={`range-${r}`}
        >
          {r}
        </button>
      ))}
    </span>
  );
}

function AddSplitButton({
  onAddManually,
  onImportCsv,
}: {
  onAddManually: () => void;
  onImportCsv: () => void;
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLSpanElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);

  return (
    <span ref={wrapRef} className="relative inline-flex">
      <button
        type="button"
        onClick={onAddManually}
        className="inline-flex items-center gap-[6px] rounded-l-md border border-[--color-accent-primary] bg-[--color-accent-primary] px-3 py-[6px] font-mono text-[10px] tracking-[0.08em] text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover]"
        data-testid="add-position-primary"
      >
        <Plus size={11} aria-hidden="true" />
        ADD POSITION
      </button>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label="Add position options"
        aria-expanded={open}
        className="inline-flex items-center justify-center rounded-r-md border border-l-0 border-[--color-accent-primary] bg-[--color-accent-primary] px-2 text-[--color-accent-on] transition-colors hover:bg-[--color-accent-hover]"
        data-testid="add-position-toggle"
      >
        <ChevronDown size={12} aria-hidden="true" />
      </button>
      {open ? (
        <ul
          role="menu"
          className="absolute right-0 top-full z-20 mt-1 w-44 overflow-hidden rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-lg"
        >
          <li
            role="menuitem"
            tabIndex={0}
            onClick={() => {
              setOpen(false);
              onAddManually();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setOpen(false);
                onAddManually();
              }
            }}
            className="cursor-pointer px-3 py-2 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover]"
            data-testid="menu-add-manually"
          >
            Add manually
          </li>
          <li
            role="menuitem"
            tabIndex={0}
            onClick={() => {
              setOpen(false);
              onImportCsv();
            }}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                setOpen(false);
                onImportCsv();
              }
            }}
            className="cursor-pointer px-3 py-2 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover]"
            data-testid="menu-import-csv"
          >
            Import CSV…
          </li>
        </ul>
      ) : null}
    </span>
  );
}
