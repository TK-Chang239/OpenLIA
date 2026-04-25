import { useCallback, useEffect, useMemo, useState } from "react";

import { runSnapshot } from "../../api/retail-sentiment";
import { EvidenceTab } from "../../components/retail-sentiment/EvidenceTab";
import { InsightsTab } from "../../components/retail-sentiment/InsightsTab";
import { MetricsDeepDive } from "../../components/retail-sentiment/MetricsDeepDive";
import { OverviewTab } from "../../components/retail-sentiment/OverviewTab";
import { ScheduleEditor } from "../../components/retail-sentiment/ScheduleEditor";
import { SettingsDrawer } from "../../components/retail-sentiment/SettingsDrawer";
import { TickerSelector } from "../../components/retail-sentiment/TickerSelector";
import { useRsConfig } from "../../hooks/useRsConfig";
import { useRsDashboard } from "../../hooks/useRsDashboard";
import { useRsHistory } from "../../hooks/useRsHistory";
import { useRsSchedule } from "../../hooks/useRsSchedule";
import { useRsSpikes } from "../../hooks/useRsSpikes";

type TabId = "overview" | "evidence" | "insights";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "evidence", label: "Evidence" },
  { id: "insights", label: "Insights" },
];

function tabFromConfig(active: string | undefined): TabId {
  if (active === "evidence" || active === "insights") return active;
  return "overview";
}

export default function RetailSentiment(): JSX.Element {
  const { config, save: saveConfig } = useRsConfig();
  const { dashboard, refresh: refreshDashboard } = useRsDashboard(
    config?.refresh_interval_minutes ?? null,
  );
  const { spikes, refresh: refreshSpikes } = useRsSpikes();
  const { schedule, save: saveSchedule } = useRsSchedule();

  const [tab, setTab] = useState<TabId>("overview");
  const [tickers, setTickers] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [deepDiveOpen, setDeepDiveOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  // Hydrate tickers + selected tab from dashboard + config.
  useEffect(() => {
    if (dashboard) {
      setTickers((prev) => {
        const merged = Array.from(new Set([...prev, ...dashboard.tickers]));
        return merged;
      });
    }
  }, [dashboard]);

  useEffect(() => {
    if (config) setTab(tabFromConfig(config.active_tab));
  }, [config]);

  const { history } = useRsHistory(selected, 7);

  const onTabChange = useCallback(
    (next: TabId) => {
      setTab(next);
      if (config && config.active_tab !== next) {
        void saveConfig({ active_tab: next });
      }
    },
    [config, saveConfig],
  );

  const onAddTicker = useCallback((t: string) => {
    setTickers((prev) => (prev.includes(t) ? prev : [...prev, t]));
    setSelected(t);
  }, []);

  const onRemoveTicker = useCallback((t: string) => {
    setTickers((prev) => prev.filter((x) => x !== t));
    setSelected((prev) => (prev === t ? null : prev));
  }, []);

  const onRun = useCallback(async () => {
    if (tickers.length === 0) {
      setError("Add at least one ticker before running a snapshot.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await runSnapshot(tickers);
      await refreshDashboard();
      await refreshSpikes();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }, [tickers, refreshDashboard, refreshSpikes]);

  const snapshots = useMemo(() => dashboard?.snapshots ?? [], [dashboard]);

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-6">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Retail Sentiment</h1>
          <p className="text-sm text-[--color-text-secondary]">
            Multi-source sentiment, buzz, and signal monitor.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setScheduleOpen(true)}
            className="rounded-md border border-[--color-border-secondary] px-2 py-1 text-xs"
          >
            Schedule
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="rounded-md border border-[--color-border-secondary] px-2 py-1 text-xs"
          >
            Settings
          </button>
          <button
            type="button"
            aria-label="Open metrics deep dive"
            onClick={() => setDeepDiveOpen(true)}
            className="rounded-md border border-[--color-border-secondary] px-2 py-1 text-xs"
          >
            ?
          </button>
        </div>
      </header>

      <TickerSelector
        tickers={tickers}
        selected={selected}
        onSelect={setSelected}
        onAdd={onAddTicker}
        onRemove={onRemoveTicker}
        onImportFromPortfolio={() => {
          // Wired hook — Portfolio fetcher integration left for follow-up.
          setError(
            "Portfolio import is wired but not yet connected to the live portfolio API.",
          );
        }}
      />

      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => onTabChange(t.id)}
            data-testid={`tab-${t.id}`}
            className={[
              "rounded-md border px-3 py-1 text-sm",
              tab === t.id
                ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
                : "border-[--color-border-subtle] bg-[--color-bg-elevated]",
            ].join(" ")}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => void onRun()}
            disabled={busy}
            className="rounded-md bg-[--color-accent-primary] px-3 py-1 text-xs text-[--color-accent-on] disabled:opacity-60"
          >
            {busy ? "Running…" : "Run snapshot"}
          </button>
          <button
            type="button"
            onClick={() => {
              void refreshDashboard();
              void refreshSpikes();
            }}
            className="rounded-md border border-[--color-border-secondary] px-3 py-1 text-xs"
          >
            Refresh
          </button>
        </div>
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="rs-error-banner"
          className="rounded-md border border-[--color-feedback-error] bg-[--color-feedback-error-bg] px-3 py-2 text-sm text-[--color-feedback-error]"
        >
          {error}
        </div>
      ) : null}

      {tickers.length === 0 ? (
        <div
          data-testid="rs-empty"
          className="rounded-md border border-dashed border-[--color-border-subtle] p-6 text-sm text-[--color-text-secondary]"
        >
          No tickers tracked. Add one above or use Import from Portfolio.
        </div>
      ) : null}

      {tab === "overview" ? (
        <OverviewTab selected={selected} snapshots={snapshots} />
      ) : null}
      {tab === "evidence" ? (
        <EvidenceTab selected={selected} history={history} />
      ) : null}
      {tab === "insights" ? (
        <InsightsTab
          selected={selected}
          snapshots={snapshots}
          spikes={spikes}
        />
      ) : null}

      <MetricsDeepDive
        open={deepDiveOpen}
        onClose={() => setDeepDiveOpen(false)}
      />
      <ScheduleEditor
        open={scheduleOpen}
        schedule={schedule}
        onClose={() => setScheduleOpen(false)}
        onSave={saveSchedule}
      />
      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSave={async (next) => {
          // Persist via the existing config endpoint as `metric_settings`.
          await saveConfig({
            metric_settings: next as unknown as Record<string, unknown>,
          });
        }}
      />
    </div>
  );
}
