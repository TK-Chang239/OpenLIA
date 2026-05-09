import { useCallback, useEffect, useMemo, useState } from "react";

import { runSnapshot } from "../../api/retail-sentiment";
import { EvidenceTab } from "../../components/retail-sentiment/EvidenceTab";
import { InsightsTab } from "../../components/retail-sentiment/InsightsTab";
import { MetricsDeepDiveTab } from "../../components/retail-sentiment/MetricsDeepDiveTab";
import { OverviewAllView } from "../../components/retail-sentiment/OverviewAllView";
import { OverviewTab } from "../../components/retail-sentiment/OverviewTab";
import { ScheduleEditor } from "../../components/retail-sentiment/ScheduleEditor";
import { SettingsDrawer } from "../../components/retail-sentiment/SettingsDrawer";
import { TickerSelector } from "../../components/retail-sentiment/TickerSelector";
import { useRsConfig } from "../../hooks/useRsConfig";
import { useRsDashboard } from "../../hooks/useRsDashboard";
import { useRsHistory } from "../../hooks/useRsHistory";
import { useRsQuotes } from "../../hooks/useRsQuotes";
import { useRsSchedule } from "../../hooks/useRsSchedule";
import { useRsSpikes } from "../../hooks/useRsSpikes";

type TabId = "overview" | "metrics" | "evidence" | "insights";

const TABS: Array<{ id: TabId; label: string }> = [
  { id: "overview", label: "Overview" },
  { id: "metrics", label: "Metrics Deep Dive" },
  { id: "evidence", label: "Evidence" },
  { id: "insights", label: "Insights" },
];

const REFRESH_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 0, label: "Off" },
  { value: 30, label: "30 min" },
  { value: 60, label: "1 hr" },
];

function tabFromConfig(active: string | undefined): TabId {
  if (
    active === "metrics" ||
    active === "evidence" ||
    active === "insights"
  )
    return active;
  return "overview";
}

const TOP_BTN =
  "inline-flex items-center gap-1.5 h-8 px-3 rounded-md border bg-transparent text-[12.5px] font-medium transition-colors duration-[--duration-normal] ease-[--ease-out] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] hover:border-[--color-border-strong]";

export default function RetailSentiment(): JSX.Element {
  const { config, save: saveConfig } = useRsConfig();
  const refreshInterval = config?.refresh_interval_minutes ?? 0;
  const { dashboard, refresh: refreshDashboard } = useRsDashboard(
    refreshInterval > 0 ? refreshInterval : null,
  );
  const { spikes, refresh: refreshSpikes } = useRsSpikes();
  const { schedule, save: saveSchedule } = useRsSchedule();

  const [tab, setTab] = useState<TabId>("overview");
  const [tickers, setTickers] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    if (dashboard) {
      setTickers((prev) =>
        Array.from(new Set([...prev, ...dashboard.tickers])),
      );
    }
  }, [dashboard]);

  useEffect(() => {
    if (config) setTab(tabFromConfig(config.active_tab));
  }, [config]);

  const { history } = useRsHistory(selected, 30);
  const { bars: quotes } = useRsQuotes(selected, 30);

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

  const onChangeRefresh = useCallback(
    (mins: number) => {
      void saveConfig({ refresh_interval_minutes: mins });
    },
    [saveConfig],
  );

  const snapshots = useMemo(() => dashboard?.snapshots ?? [], [dashboard]);
  const selectedSnapshot = useMemo(
    () =>
      selected ? snapshots.find((s) => s.ticker === selected) ?? null : null,
    [selected, snapshots],
  );

  const sourceCount = useMemo(() => {
    const set = new Set<string>();
    for (const s of snapshots) {
      for (const k of Object.keys(s.source_breakdown ?? {})) set.add(k);
    }
    return set.size;
  }, [snapshots]);

  return (
    <div
      className="flex flex-col h-full animate-rs-page-enter"
      data-testid="retail-sentiment"
    >
      {/* Top bar */}
      <header
        className="flex items-center px-6 flex-shrink-0"
        style={{
          height: 52,
          borderBottom: "1px solid var(--color-border-subtle)",
          background: "var(--color-bg-base)",
          gap: 14,
        }}
      >
        <span
          className="text-[--color-text-primary]"
          style={{
            fontSize: 20,
            fontWeight: 600,
            letterSpacing: "-0.01em",
          }}
        >
          Retail Sentiment
        </span>
        <span
          className="font-mono"
          style={{
            fontSize: 10,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--color-text-tertiary)",
            marginLeft: 14,
            paddingLeft: 14,
            borderLeft: "1px solid var(--color-border-subtle)",
          }}
        >
          Department ·{" "}
          <strong
            style={{
              color: "var(--color-feedback-success)",
              fontWeight: 500,
            }}
          >
            Active
          </strong>
        </span>
        <div className="flex-1" />
        {sourceCount > 0 ? (
          <span
            className="inline-flex items-center gap-1.5 font-mono"
            style={{
              height: 24,
              padding: "0 9px",
              borderRadius: 4,
              background: "rgba(212,255,0,0.12)",
              border: "1px solid rgba(212,255,0,0.25)",
              fontSize: 10,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--color-feedback-success)",
            }}
          >
            <span
              className="inline-block animate-rs-live-pulse"
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--color-accent-primary)",
                boxShadow: "0 0 6px rgba(212,255,0,0.7)",
              }}
              aria-hidden="true"
            />
            Streaming · {sourceCount} sources
          </span>
        ) : null}
        <label className="inline-flex items-center gap-2">
          <span
            className="rs-mono-label"
            style={{ color: "var(--color-text-secondary)" }}
          >
            Auto-refresh
          </span>
          <select
            value={refreshInterval}
            onChange={(e) => onChangeRefresh(Number(e.target.value))}
            data-testid="rs-refresh-select"
            className="h-8 px-2 rounded-md border bg-[--color-bg-input] text-[12px] font-mono"
            style={{ borderColor: "var(--color-border-secondary)" }}
          >
            {REFRESH_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={() => void onRun()}
          disabled={busy}
          data-testid="rs-run-snapshot"
          className="inline-flex items-center h-8 px-3 rounded-md text-[12.5px] font-medium disabled:opacity-60"
          style={{
            background: "var(--color-accent-primary)",
            color: "var(--color-accent-on)",
          }}
        >
          {busy ? "Running…" : "Run snapshot"}
        </button>
        <button
          type="button"
          onClick={() => setScheduleOpen(true)}
          className={TOP_BTN}
          style={{
            borderColor: "var(--color-border-subtle)",
            color: "var(--color-text-secondary)",
          }}
        >
          Schedule
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className={TOP_BTN}
          style={{
            borderColor: "var(--color-border-subtle)",
            color: "var(--color-text-secondary)",
          }}
        >
          Settings
        </button>
      </header>

      {/* Tab bar */}
      <nav
        className="flex items-stretch px-6 flex-shrink-0 gap-1"
        style={{
          height: 44,
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        {TABS.map((t) => {
          const active = tab === t.id;
          return (
            <button
              key={t.id}
              type="button"
              onClick={() => onTabChange(t.id)}
              data-testid={`tab-${t.id}`}
              className="group relative inline-flex items-center px-3.5 h-full bg-transparent border-0 text-[13.5px] cursor-pointer transition-colors duration-[--duration-normal] hover:bg-[--color-surface-hover]"
              style={{
                color: active
                  ? "var(--color-text-primary)"
                  : "var(--color-text-secondary)",
                fontWeight: active ? 500 : undefined,
              }}
            >
              {t.label}
              {active ? (
                <span
                  aria-hidden="true"
                  className="absolute left-0 right-0 -bottom-px"
                  style={{
                    height: 2,
                    background: "var(--color-text-primary)",
                  }}
                />
              ) : null}
            </button>
          );
        })}
      </nav>

      {/* Ticker selector */}
      <div
        className="px-6 py-3 flex-shrink-0"
        style={{
          borderBottom: "1px solid var(--color-border-subtle)",
        }}
      >
        <TickerSelector
          tickers={tickers}
          selected={selected}
          onSelect={setSelected}
          onAdd={onAddTicker}
          onRemove={onRemoveTicker}
          onImportFromPortfolio={() => {
            setError(
              "Portfolio import is wired but not yet connected to the live portfolio API.",
            );
          }}
        />
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="rs-error-banner"
          className="mx-6 mt-3 rounded-md border px-3 py-2 text-[12.5px]"
          style={{
            borderColor: "var(--color-feedback-error)",
            color: "var(--color-feedback-error)",
            background: "var(--color-bg-base)",
          }}
        >
          {error}
        </div>
      ) : null}

      {/* Body */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ scrollbarGutter: "stable" }}
      >
        <div
          key={tab}
          className="max-w-[1200px] mx-auto px-8 pt-7 pb-16 animate-rs-tab-enter"
        >
          {tab === "overview" ? (
            selected ? (
              selectedSnapshot ? (
                <OverviewTab
                  selected={selected}
                  snapshot={selectedSnapshot}
                  history={history}
                  quotes={quotes}
                />
              ) : (
                <div
                  className="rs-col-card p-8 text-center"
                  style={{ borderRadius: 12 }}
                  data-testid="overview-empty"
                >
                  <p className="rs-mono-label">No snapshot for {selected}</p>
                  <p
                    className="m-0 mt-2"
                    style={{
                      color: "var(--color-text-secondary)",
                      fontSize: 13.5,
                    }}
                  >
                    Run a snapshot from the toolbar above to populate this view.
                  </p>
                </div>
              )
            ) : (
              <OverviewAllView
                snapshots={snapshots}
                spikes={spikes}
                onPickTicker={setSelected}
              />
            )
          ) : null}
          {tab === "metrics" ? (
            <MetricsDeepDiveTab selected={selected} history={history} />
          ) : null}
          {tab === "evidence" ? (
            <EvidenceTab selected={selected} history={history} />
          ) : null}
          {tab === "insights" ? (
            <InsightsTab
              selected={selected}
              snapshots={snapshots}
              spikes={spikes}
              onPickTicker={setSelected}
            />
          ) : null}
        </div>
      </div>

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
          await saveConfig({
            metric_settings: next as unknown as Record<string, unknown>,
          });
        }}
      />
    </div>
  );
}
