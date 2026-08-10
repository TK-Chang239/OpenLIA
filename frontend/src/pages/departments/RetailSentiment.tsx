import { useState } from "react";
import { useTranslation } from "react-i18next";

import { TickerSelector } from "../../components/retail-sentiment/TickerSelector";
import RsOverviewView from "./retail_sentiment/RsOverviewView";
import RsSettingsPanel from "./retail_sentiment/RsSettingsPanel";

function SettingsIcon(): JSX.Element {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-3.5 w-3.5"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4" />
    </svg>
  );
}

// Demo mode pre-seeds a watchlist so the dashboard is populated on load (the
// real app starts empty and the user adds tickers). No-op in normal builds.
const DEMO_TICKERS =
  import.meta.env.VITE_DEMO_MODE === "true" ? ["NVDA", "AAPL", "PLTR"] : [];

export default function RetailSentiment(): JSX.Element {
  const { t } = useTranslation();
  const [tickers, setTickers] = useState<string[]>(DEMO_TICKERS);
  const [selected, setSelected] = useState<string | null>(DEMO_TICKERS[0] ?? null);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const onAddTicker = (ticker: string) => {
    setTickers((prev) => (prev.includes(ticker) ? prev : [...prev, ticker]));
    setSelected(ticker);
  };

  const onRemoveTicker = (ticker: string) => {
    setTickers((prev) => prev.filter((x) => x !== ticker));
    setSelected((prev) => (prev === ticker ? (tickers.find((t) => t !== ticker) ?? null) : prev));
  };

  return (
    <div
      className="flex flex-col h-full animate-rs-page-enter"
      data-testid="retail-sentiment"
    >
      {/* Top bar */}
      <header
        className="flex items-center flex-shrink-0 gap-3 px-6 border-b border-[--color-border-subtle] bg-[--color-bg-base]"
        style={{ height: 52 }}
      >
        <span
          className="text-[--color-text-primary]"
          style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em" }}
        >
          {t("retail_sentiment.title")}
        </span>
        <span
          className="font-mono ml-3 pl-3 border-l border-[--color-border-subtle]"
          style={{
            fontSize: 10,
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            color: "var(--color-text-tertiary)",
          }}
        >
          {t("retail_sentiment.department_label")} ·{" "}
          <strong style={{ color: "var(--color-feedback-success)", fontWeight: 500 }}>
            <span
              aria-hidden="true"
              className="mr-1 inline-block h-[6px] w-[6px] rounded-full bg-[--color-feedback-success] align-middle animate-rs-live-pulse"
            />
            {t("retail_sentiment.status_active")}
          </strong>
        </span>
        <div className="flex-1" />
        <button
          type="button"
          data-testid="rs-settings-button"
          onClick={() => setSettingsOpen(true)}
          className="inline-flex h-[30px] items-center gap-1.5 rounded-md border border-[--color-border-subtle] bg-transparent px-3 font-mono text-[12px] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
        >
          <SettingsIcon />
          {t("retail_sentiment.settings")}
        </button>
      </header>

      {/* Ticker selector */}
      <div
        className="flex-shrink-0 px-6 py-3 border-b border-[--color-border-subtle]"
      >
        <TickerSelector
          tickers={tickers}
          selected={selected}
          onSelect={setSelected}
          onAdd={onAddTicker}
          onRemove={onRemoveTicker}
          onImportFromPortfolio={undefined}
        />
      </div>

      {/* Body */}
      <div
        className="flex-1 overflow-y-auto"
        style={{ scrollbarGutter: "stable" }}
      >
        <div
          key={selected ?? "empty"}
          className="max-w-[1200px] mx-auto px-8 pt-7 pb-16 animate-rs-section-enter"
        >
          {selected ? (
            <RsOverviewView key={selected} ticker={selected} />
          ) : (
            <div
              className="rs-col-card p-10 text-center space-y-2"
              style={{ borderRadius: 12 }}
              data-testid="rs-empty-watchlist"
            >
              <p className="font-mono text-[11px] uppercase tracking-[0.14em] text-[--color-text-tertiary]">
                Retail Sentiment
              </p>
              <p className="text-[15px] text-[--color-text-secondary]">
                Add a ticker above to view the sentiment dashboard for that name.
              </p>
            </div>
          )}
        </div>
      </div>

      {settingsOpen ? (
        <RsSettingsPanel onClose={() => setSettingsOpen(false)} />
      ) : null}
    </div>
  );
}
