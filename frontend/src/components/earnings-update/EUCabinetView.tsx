import { useEffect, useMemo, useRef, useState } from "react";

import { RecentReport } from "../../api/earnings-update";
import { ConfirmDialog } from "../primitives/ConfirmDialog";

import { ReportRowItem } from "./ReportRowItem";

interface Props {
  reports: RecentReport[];
  onBack: () => void;
  onOpenReport: (id: string) => void;
  onRemove: (id: string) => Promise<void>;
  onQueryChange?: (q: string, ticker: string) => void;
}

function monthKey(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

export function EUCabinetView({
  reports,
  onBack,
  onOpenReport,
  onRemove,
  onQueryChange,
}: Props) {
  const [q, setQ] = useState("");
  const [ticker, setTicker] = useState("");
  const [filterOpen, setFilterOpen] = useState(false);
  const [pendingRemoval, setPendingRemoval] = useState<string | null>(null);
  const debounceRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!onQueryChange) return;
    if (debounceRef.current !== undefined) {
      window.clearTimeout(debounceRef.current);
    }
    debounceRef.current = window.setTimeout(() => {
      onQueryChange(q, ticker);
    }, 300);
    return () => {
      if (debounceRef.current !== undefined) {
        window.clearTimeout(debounceRef.current);
      }
    };
  }, [q, ticker, onQueryChange]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    const tickerFilter = ticker.trim().toUpperCase();
    return reports.filter((r) => {
      if (tickerFilter && (r.subject ?? "").toUpperCase() !== tickerFilter) {
        return false;
      }
      if (!needle) return true;
      return (
        (r.subject ?? "").toLowerCase().includes(needle) ||
        r.title.toLowerCase().includes(needle)
      );
    });
  }, [q, ticker, reports]);

  const groups = useMemo(() => {
    const acc: Record<string, RecentReport[]> = {};
    for (const r of filtered) {
      const k = monthKey(r.created_at);
      (acc[k] ??= []).push(r);
    }
    return Object.entries(acc);
  }, [filtered]);

  return (
    <div className="fixed inset-0 bg-[--color-bg-base] z-50 overflow-y-auto sm:inset-0">
      <header className="flex items-center justify-between h-14 px-4 sm:px-6 border-b border-[--color-border-subtle]">
        <button
          type="button"
          onClick={onBack}
          className="text-sm text-[--color-accent-primary]"
        >
          ← Back to Earnings Updates
        </button>
        <h2 className="text-xl font-semibold">EU Cabinet</h2>
        <span className="w-32" />
      </header>
      <div className="px-4 sm:px-6 py-4 flex items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search reports..."
          className="flex-1 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 text-sm text-[--color-text-primary]"
        />
        <button
          type="button"
          onClick={() => setFilterOpen((v) => !v)}
          aria-expanded={filterOpen}
          className="text-sm border border-[--color-border-subtle] rounded-[--radius-md] px-3 h-9 hover:bg-[--color-surface-hover]"
        >
          Filters ▾
        </button>
      </div>
      {filterOpen ? (
        <div className="px-4 sm:px-6 pb-4 flex flex-wrap items-center gap-2">
          <label className="text-xs text-[--color-text-secondary]">Ticker</label>
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
            placeholder="AAPL"
            className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-sm] px-2 h-8 text-sm text-[--color-text-primary] w-24"
          />
        </div>
      ) : null}
      {groups.map(([k, items]) => (
        <div key={k}>
          <h3 className="text-sm font-medium text-[--color-text-secondary] px-4 sm:px-6 py-2">
            {k}
          </h3>
          {items.map((r) => (
            <ReportRowItem
              key={r.id}
              report={r}
              onOpen={onOpenReport}
              showExtras
              onRemove={(id) => setPendingRemoval(id)}
            />
          ))}
        </div>
      ))}
      <ConfirmDialog
        open={pendingRemoval !== null}
        title="Remove report?"
        description="This action cannot be undone."
        confirmLabel="Remove"
        destructive
        onCancel={() => setPendingRemoval(null)}
        onConfirm={() => {
          const id = pendingRemoval;
          setPendingRemoval(null);
          if (id) void onRemove(id);
        }}
      />
    </div>
  );
}
