import { useEffect, useState } from "react";
import type { JSX, ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";

import {
  createGroup,
  createHolding,
  fetchGroups,
  fetchPortfolioPrefs,
  refreshPrices,
  updatePortfolioPrefs,
  type PortfolioHolding,
  type RefreshCadence,
} from "../api/portfolio";
import type { Market } from "./marketTypes";
import { MARKET_LABELS } from "./marketTypes";
import { exportCsvUrl } from "../api/portfolio";
import { ToastProvider, useToast } from "../components/primitives/Toast";

import { AddEditDrawer } from "./AddEditDrawer";
import { HoldingDetailDrawer } from "./HoldingDetailDrawer";
import { HoldingsTable } from "./HoldingsTable";
import { ImportCsvDialog } from "./ImportCsvDialog";
import { KpiBand } from "./KpiBand";
import { LiaAlertsCard } from "./LiaAlertsCard";
import { PerfChart } from "./PerfChart";
import { PortfolioAllocationCard } from "./PortfolioAllocationCard";
import {
  PortfolioPageHeader,
  type PerfRange,
} from "./PortfolioPageHeader";
import { useAnalytics } from "./useAnalytics";
import { useHoldings } from "./useHoldings";
import { useSparklines } from "./useSparklines";
import { useValueSeries } from "./useValueSeries";

function ShellInner({ market }: { market: Market }): JSX.Element {
  const { t } = useTranslation();
  const toast = useToast();
  const navigate = useNavigate();
  const { holdings, loading, reload, remove } = useHoldings(market);
  const { analytics, refresh } = useAnalytics(market);
  const [groups, setGroups] = useState<string[]>([]);

  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<PortfolioHolding | null>(null);
  const [csvOpen, setCsvOpen] = useState(false);
  const [drawer, setDrawer] = useState<PortfolioHolding | null>(null);
  const [range, setRange] = useState<PerfRange>("1W");
  const { series: valueSeries, loading: valueSeriesLoading } = useValueSeries(
    range,
    market,
  );
  const { data: sparklines } = useSparklines(market);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshCadence, setRefreshCadence] = useState<RefreshCadence>("daily");

  useEffect(() => {
    void fetchGroups()
      .then(setGroups)
      .catch(() => setGroups([]));
    void fetchPortfolioPrefs()
      .then((p) => setRefreshCadence(p.refresh_cadence))
      .catch(() => {
        /* keep default */
      });
  }, []);

  const onCadenceChange = (next: RefreshCadence) => {
    setRefreshCadence(next);
    void updatePortfolioPrefs({ refresh_cadence: next }).catch((e) => {
      toast.push({
        title: t("portfolio_page.failed_save_cadence", { message: (e as Error).message }),
        tone: "error",
      });
    });
  };

  const reloadGroups = async () => {
    try {
      const next = await fetchGroups();
      setGroups(next);
    } catch {
      /* keep prior groups */
    }
  };

  const onRefresh = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      const result = await refreshPrices(market);
      await refresh();
      const failed = result.failed ?? [];
      if (failed.length > 0) {
        toast.push({
          title: t("portfolio_page.prices_refresh_failed", { tickers: failed.join(", ") }),
          tone: "error",
        });
      } else {
        toast.push({ title: t("portfolio_page.prices_refreshed"), tone: "success" });
      }
    } catch (e) {
      const err = e as Error & { retryAfter?: number; status?: number };
      const msg =
        err.status === 429 && err.retryAfter
          ? t("portfolio_page.retry_in_seconds", { seconds: err.retryAfter })
          : err.message;
      toast.push({ title: msg, tone: "error" });
    } finally {
      setRefreshing(false);
    }
  };

  const onCreateGroupInline = async (name: string) => {
    const next = await createGroup(name);
    setGroups(next);
  };

  const onRowClick = (h: PortfolioHolding) => {
    setDrawer(h);
  };

  const onDrawerEdit = (h: PortfolioHolding) => {
    setDrawer(null);
    setEditTarget(h);
  };

  const onDrawerRemove = async (h: PortfolioHolding) => {
    setDrawer(null);
    const snapshot = await remove(h.id);
    if (!snapshot) return;
    toast.push({
      title: t("portfolio_page.removed_undo", { ticker: snapshot.ticker }),
      tone: "info",
      durationMs: 5000,
      undo: {
        label: t("portfolio_page.undo"),
        onClick: () => {
          void createHolding(
            {
              ticker: snapshot.ticker,
              shares: snapshot.shares ?? null,
              cost_basis: snapshot.cost_basis ?? null,
              currency: snapshot.currency,
              notes: snapshot.notes_text ?? null,
              groups: snapshot.groups,
            },
            market,
          ).then(() => reload());
        },
      },
    });
  };

  return (
    <div className="min-h-full overflow-x-hidden bg-[--color-bg-base]" data-testid="portfolio-page">
      <div className="mx-auto grid max-w-[1400px] grid-cols-1 gap-[18px] px-7 py-6 [@media(min-width:1100px)]:grid-cols-[1fr_320px]">
        <div className="flex min-w-0 flex-col gap-[18px]">
          <Reveal delay={0}>
            <PortfolioPageHeader
              holdingCount={holdings.length}
              lastSyncedAt={analytics?.last_quote_at ?? null}
              refreshing={refreshing}
              onRefresh={() => void onRefresh()}
              range={range}
              onRangeChange={setRange}
              exportHref={exportCsvUrl()}
              onAddManually={() => setAddOpen(true)}
              onImportCsv={() => setCsvOpen(true)}
              refreshCadence={refreshCadence}
              onRefreshCadenceChange={onCadenceChange}
              market={market}
              marketLabel={MARKET_LABELS[market]}
              onMarketChange={(next) => navigate(`/portfolio/${next}`)}
            />
          </Reveal>

          <Reveal delay={1}>
            <KpiBand analytics={analytics} loading={loading && holdings.length === 0} />
          </Reveal>

          {(analytics?.currencies_present?.length ?? 0) > 1 ? (
            <Reveal delay={1}>
              <div
                className="rounded-md border border-[--color-feedback-error] bg-[--color-bg-elevated] px-4 py-2 text-xs text-[--color-text-secondary]"
                data-testid="mixed-currency-banner"
              >
                {t("portfolio_page.fx_unavailable", {
                  currencies: analytics?.currencies_present?.join(", ") ?? "",
                  display: analytics?.display_currency ?? "USD",
                })}
              </div>
            </Reveal>
          ) : null}

          <Reveal delay={2}>
            <PerfChart range={range} series={valueSeries} loading={valueSeriesLoading} market={market} />
          </Reveal>

          {valueSeries && valueSeries.period_return_pct !== null ? (
            <Reveal delay={2}>
              <div
                className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-4 py-2 text-sm text-[--color-text-secondary]"
                data-testid="period-return-banner"
              >
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                  {range} {t("portfolio_page.period_return")} ·{" "}
                  {valueSeries.actual_span
                    ? t("portfolio_page.since", { date: valueSeries.actual_span.start })
                    : ""}
                </span>{" "}
                <span
                  className={
                    Number(valueSeries.period_return_pct) >= 0
                      ? "text-[--color-feedback-success]"
                      : "text-[--color-feedback-error]"
                  }
                >
                  {Number(valueSeries.period_return_pct) >= 0 ? "+" : ""}
                  {(Number(valueSeries.period_return_pct) * 100).toFixed(2)}%
                </span>
              </div>
            </Reveal>
          ) : null}

          <Reveal delay={3}>
            <HoldingsTable
              holdings={holdings}
              analytics={analytics}
              groups={groups}
              loading={loading && holdings.length === 0}
              selectedHoldingId={drawer?.id ?? null}
              sparklines={sparklines}
              onRowClick={onRowClick}
              onManageGroups={() => {
                toast.push({
                  title: t("portfolio_page.manage_groups_hint"),
                  tone: "info",
                  durationMs: 4000,
                });
              }}
            />
          </Reveal>
        </div>

        <aside className="flex flex-col gap-[18px] [@media(min-width:1100px)]:sticky [@media(min-width:1100px)]:top-6 [@media(min-width:1100px)]:self-start">
          <Reveal delay={2}>
            <PortfolioAllocationCard holdings={holdings} analytics={analytics} />
          </Reveal>
          <Reveal delay={3}>
            <LiaAlertsCard hasHoldings={holdings.length > 0} />
          </Reveal>
        </aside>
      </div>

      <AddEditDrawer
        open={addOpen || editTarget !== null}
        mode={editTarget ? "edit" : "create"}
        initial={editTarget}
        groups={groups}
        market={market}
        onCreateGroup={onCreateGroupInline}
        onClose={() => {
          setAddOpen(false);
          setEditTarget(null);
        }}
        onSaved={async () => {
          await reload();
          await reloadGroups();
          toast.push({ title: t("portfolio_page.holding_saved"), tone: "success" });
        }}
      />

      <ImportCsvDialog
        open={csvOpen}
        onClose={() => setCsvOpen(false)}
        onImported={async (res) => {
          if (res.created.length) await reload();
          toast.push({
            title: t("portfolio_page.import_summary", {
              created: res.created.length,
              errors: res.errors.length,
            }),
            tone: res.errors.length ? "error" : "success",
          });
        }}
      />

      <HoldingDetailDrawer
        open={drawer !== null}
        holding={drawer}
        analytics={analytics}
        onClose={() => setDrawer(null)}
        onEdit={onDrawerEdit}
        onRemove={(h) => void onDrawerRemove(h)}
      />
    </div>
  );
}

export function PortfolioShell({ market }: { market: Market }): JSX.Element {
  return (
    <ToastProvider>
      <ShellInner key={market} market={market} />
    </ToastProvider>
  );
}

const STAGGER = 0.06;

function Reveal({
  delay,
  children,
}: {
  delay: number;
  children: ReactNode;
}): JSX.Element {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.32, ease: "easeOut", delay: delay * STAGGER }}
    >
      {children}
    </motion.div>
  );
}
