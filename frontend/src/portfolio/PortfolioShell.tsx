import { Download, Plus, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  createGroup,
  createHolding,
  deleteGroup,
  exportCsvUrl,
  fetchGroups,
  renameGroup,
  updateHolding,
  type PortfolioHolding,
} from "../api/portfolio";
import { ToastProvider, useToast } from "../components/primitives/Toast";
import { AddEditDrawer } from "./AddEditDrawer";
import { AnalyticsCards } from "./AnalyticsCards";
import { EmptyState } from "./EmptyState";
import { ALL_GROUP, GroupTabs } from "./GroupTabs";
import { HoldingsGrid } from "./HoldingsGrid";
import { HoldingsList } from "./HoldingsList";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { PriceRefreshButton } from "./PriceRefreshButton";
import { SearchAndAdd } from "./SearchAndAdd";
import { SortControl } from "./SortControl";
import { useAnalytics } from "./useAnalytics";
import { useHoldings } from "./useHoldings";
import { useLocalPref } from "./useLocalPref";
import { useSortedHoldings } from "./useSortedHoldings";
import { ViewToggle, type ViewMode } from "./ViewToggle";

function MarketClosedIndicator({ at }: { readonly at: string | null | undefined }): JSX.Element | null {
  if (!at) return null;
  const ts = Date.parse(at);
  if (!Number.isFinite(ts)) return null;
  const now = Date.now();
  const stale = now - ts > 15 * 60 * 1000; // 15min stale → market closed
  if (!stale) return null;
  return (
    <span className="text-xs text-[--color-text-tertiary]" data-testid="market-closed">
      Market closed
    </span>
  );
}

function ShellInner(): JSX.Element {
  const toast = useToast();
  const { holdings, loading, reload, remove } = useHoldings();
  const { analytics, refresh } = useAnalytics();
  const [groups, setGroups] = useState<string[]>([]);
  const [activeGroup, setActiveGroup] = useState<string>(ALL_GROUP);
  const [view, setView] = useLocalPref<ViewMode>("portfolio:view", "list");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);

  useEffect(() => {
    void fetchGroups()
      .then(setGroups)
      .catch(() => setGroups([]));
  }, []);

  const filteredHoldings = useMemo(() => {
    if (activeGroup === ALL_GROUP) return holdings;
    return holdings.filter((h) => h.groups.includes(activeGroup));
  }, [holdings, activeGroup]);

  const analyticsByHolding = useMemo(() => {
    const map = new Map<string, NonNullable<typeof analytics>["positions"][number] | undefined>();
    analytics?.positions.forEach((p) => map.set(p.holding_id, p));
    return map;
  }, [analytics]);

  const { sorted, sortKey, setSortKey } = useSortedHoldings(
    filteredHoldings,
    analyticsByHolding,
    activeGroup,
  );

  const existingTickers = useMemo(
    () => new Set(holdings.map((h) => h.ticker)),
    [holdings],
  );

  const onAdded = async (ticker: string) => {
    await reload();
    toast.push({ title: `${ticker} added to Portfolio`, tone: "success" });
  };

  const onRemove = async (id: string) => {
    const snapshot = await remove(id);
    if (!snapshot) return;
    toast.push({
      title: `${snapshot.ticker} removed`,
      tone: "info",
      durationMs: 5000,
      undo: {
        label: "Undo",
        onClick: () => {
          void createHolding({
            ticker: snapshot.ticker,
            shares: snapshot.shares ?? null,
            cost_basis: snapshot.cost_basis ?? null,
            currency: snapshot.currency,
            notes: snapshot.notes_text ?? null,
            groups: snapshot.groups,
          }).then(() => reload());
        },
      },
    });
  };

  const onCreateGroup = async (name: string) => {
    const next = await createGroup(name);
    setGroups(next);
  };

  const onRenameGroup = async (oldName: string, newName: string) => {
    const next = await renameGroup(oldName, newName);
    setGroups(next);
    await reload();
  };

  const onDeleteGroup = async (name: string) => {
    // Snapshot members for Undo restoration of group membership.
    const affected: PortfolioHolding[] = holdings.filter((h) =>
      h.groups.includes(name),
    );
    const next = await deleteGroup(name);
    setGroups(next);
    await reload();
    toast.push({
      title: `Group '${name}' deleted`,
      tone: "info",
      durationMs: 5000,
      undo: {
        label: "Undo",
        onClick: () => {
          void createGroup(name).then(async () => {
            for (const h of affected) {
              const groups = Array.from(new Set([...h.groups, name]));
              try {
                await updateHolding(h.id, { groups });
              } catch {
                /* swallow */
              }
            }
            await reload();
            const fresh = await fetchGroups();
            setGroups(fresh);
          });
        },
      },
    });
  };

  return (
    <div className="p-6 space-y-5" data-testid="portfolio-page">
      <header className="flex items-center justify-between gap-3 flex-wrap">
        <h1 className="text-2xl font-semibold text-[--color-text-primary]">Portfolio</h1>
        <div className="flex items-center gap-2">
          <PriceRefreshButton
            onRefresh={refresh}
            onSuccess={() => toast.push({ title: "Prices refreshed", tone: "success" })}
            onRateLimited={(s) =>
              toast.push({ title: `Try again in ${s} seconds`, tone: "error" })
            }
          />
          <button
            type="button"
            onClick={() => setDrawerOpen(true)}
            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm]"
            data-testid="open-drawer"
          >
            <Plus size={14} aria-hidden="true" /> Add
          </button>
          <button
            type="button"
            onClick={() => setCsvOpen(true)}
            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm]"
            data-testid="open-csv"
          >
            <Upload size={14} aria-hidden="true" /> Import CSV
          </button>
          <a
            href={exportCsvUrl()}
            className="inline-flex items-center gap-1 px-3 py-1 text-sm border border-[--color-border-subtle] rounded-[--radius-sm]"
          >
            <Download size={14} aria-hidden="true" /> Export
          </a>
        </div>
      </header>

      <SearchAndAdd
        groups={groups}
        existingTickers={existingTickers}
        onAdded={onAdded}
      />

      <AnalyticsCards analytics={analytics} />

      <GroupTabs
        groups={groups}
        active={activeGroup}
        onSelect={setActiveGroup}
        onCreate={onCreateGroup}
        onRename={onRenameGroup}
        onDelete={onDeleteGroup}
      />

      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <SortControl value={sortKey} onChange={setSortKey} />
          <MarketClosedIndicator at={analytics?.last_quote_at ?? null} />
        </div>
        <ViewToggle value={view} onChange={setView} />
      </div>

      <section
        className="transition-opacity duration-150"
        data-testid="holdings-section"
        data-view={view}
      >
        {loading ? (
          <ul aria-label="Loading" className="space-y-2" data-testid="holdings-loading">
            {[0, 1, 2].map((i) => (
              <li
                key={i}
                className="h-[60px] rounded bg-[--color-border-subtle] animate-pulse"
              />
            ))}
          </ul>
        ) : sorted.length === 0 ? (
          <EmptyState />
        ) : view === "list" ? (
          <HoldingsList
            holdings={sorted}
            analyticsByHolding={analyticsByHolding}
            onRemove={onRemove}
          />
        ) : (
          <HoldingsGrid
            holdings={sorted}
            analyticsByHolding={analyticsByHolding}
            activeGroup={activeGroup}
            onRemove={onRemove}
          />
        )}
      </section>

      <AddEditDrawer
        open={drawerOpen}
        mode="create"
        onClose={() => setDrawerOpen(false)}
        onSaved={async () => {
          await reload();
          toast.push({ title: "Holding saved", tone: "success" });
        }}
      />

      <ImportCsvDialog
        open={csvOpen}
        onClose={() => setCsvOpen(false)}
        onImported={async (res) => {
          if (res.created.length) await reload();
          toast.push({
            title: `Imported ${res.created.length}; ${res.errors.length} errors`,
            tone: res.errors.length ? "error" : "success",
          });
        }}
      />
    </div>
  );
}

export function PortfolioShell(): JSX.Element {
  return (
    <ToastProvider>
      <ShellInner />
    </ToastProvider>
  );
}
