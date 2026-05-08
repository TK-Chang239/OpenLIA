import { useMemo } from "react";

import type { RsSnapshot, RsSpike } from "../../api/retail-sentiment";
import { RS_METRIC_CATALOG } from "../../lib/retail-sentiment/metric-catalog";
import { Spark } from "./charts";
import { SentimentGauge } from "./SentimentGauge";

interface Props {
  snapshots: RsSnapshot[];
  spikes: RsSpike[];
  onPickTicker: (ticker: string) => void;
}

function SectionLabel({
  title,
  meta,
  first,
}: {
  title: string;
  meta?: string;
  first?: boolean;
}) {
  return (
    <div className={`rs-sec-label ${first ? "first" : ""}`}>
      <span>{title}</span>
      <span className="rs-rule" aria-hidden="true" />
      {meta ? <span>{meta}</span> : null}
    </div>
  );
}

function metricValue(s: RsSnapshot, field: string): number | null {
  const v = (s as unknown as Record<string, number | null>)[field];
  return v === null || v === undefined || !Number.isFinite(v as number)
    ? null
    : (v as number);
}

function HeatCell({
  value,
  field,
}: {
  value: number | null;
  field: string;
}) {
  if (value === null) {
    return (
      <span
        className="rs-mono-value text-[11px]"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        —
      </span>
    );
  }
  // Normalize to a -1..1 visual band per metric for color coding.
  let band = 0;
  if (field === "sentiment_score") band = Math.max(-1, Math.min(1, value));
  else if (field === "sentiment_momentum")
    band = Math.max(-1, Math.min(1, value / 0.3));
  else if (field === "buzz_sentiment_divergence")
    band = Math.max(-1, Math.min(1, value / 2));
  else if (field === "buzz_volume")
    band = Math.max(-1, Math.min(1, (value - 1) / 1.5));
  else if (field === "bull_bear_ratio")
    band = Math.max(-1, Math.min(1, (value - 0.5) * 2));
  else if (field === "cross_source_agreement")
    band = Math.max(-1, Math.min(1, value * 2 - 1));
  else band = 0;

  const color =
    band > 0.2
      ? "var(--color-feedback-success)"
      : band < -0.2
        ? "var(--color-feedback-error)"
        : "var(--color-text-secondary)";

  return (
    <span className="rs-mono-value text-[11px]" style={{ color }}>
      {value.toFixed(2)}
    </span>
  );
}

function TrendingRail({
  snapshots,
  onPick,
}: {
  snapshots: RsSnapshot[];
  onPick: (t: string) => void;
}) {
  const top = useMemo(
    () =>
      [...snapshots]
        .sort((a, b) => (b.buzz_volume ?? 0) - (a.buzz_volume ?? 0))
        .slice(0, 6),
    [snapshots],
  );
  if (top.length === 0) return null;
  return (
    <div
      className="grid gap-2"
      style={{ gridTemplateColumns: `repeat(${top.length}, minmax(0,1fr))` }}
      data-testid="rs-trending-rail"
    >
      {top.map((s, i) => {
        const bull = Math.max(0, Math.min(1, s.bull_bear_ratio ?? 0.5)) * 100;
        const bear = 100 - bull;
        const tone =
          s.sentiment_score > 0.1
            ? "pos"
            : s.sentiment_score < -0.1
              ? "neg"
              : "neutral";
        return (
          <button
            type="button"
            key={s.ticker}
            onClick={() => onPick(s.ticker)}
            className="rs-col-card text-left p-3 hover:border-[--color-accent-primary] transition-colors duration-[--duration-normal] ease-[--ease-out]"
            style={{ borderRadius: "10px" }}
            data-testid={`rs-trending-${s.ticker}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono font-semibold text-[13px] tracking-[0.02em] text-[--color-text-primary]">
                {s.ticker}
              </span>
              <span className="rs-mono-label">#{i + 1}</span>
            </div>
            <div className="rs-mono-value text-[11px] mt-1.5">
              <strong className="font-medium">
                {(s.buzz_count ?? 0).toLocaleString()}
              </strong>{" "}
              <span style={{ color: "var(--color-text-tertiary)" }}>
                mentions
              </span>
            </div>
            <div
              className="flex h-1 my-2 rounded-full overflow-hidden"
              style={{ background: "var(--color-bg-code)" }}
              aria-hidden="true"
            >
              <span
                style={{
                  width: `${bull}%`,
                  background: "var(--color-feedback-success)",
                }}
              />
              <span
                style={{
                  width: `${bear}%`,
                  background: "var(--color-feedback-error)",
                  marginLeft: "auto",
                }}
              />
            </div>
            <div className="flex items-center justify-between rs-mono-label">
              <span
                style={{
                  color:
                    tone === "pos"
                      ? "var(--color-feedback-success)"
                      : tone === "neg"
                        ? "var(--color-feedback-error)"
                        : "var(--color-text-secondary)",
                }}
              >
                {s.sentiment_score >= 0 ? "+" : ""}
                {s.sentiment_score.toFixed(2)}
              </span>
              <span style={{ color: "var(--color-text-tertiary)" }}>
                {(s.buzz_volume ?? 0).toFixed(1)}×
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function OverviewAllView({ snapshots, spikes, onPickTicker }: Props) {
  const valid = snapshots.filter((s) => Number.isFinite(s.sentiment_score));
  const meanSentiment =
    valid.length > 0
      ? valid.reduce((a, s) => a + s.sentiment_score, 0) / valid.length
      : 0;
  const meanBuzz =
    valid.length > 0
      ? valid.reduce((a, s) => a + (s.buzz_volume ?? 0), 0) / valid.length
      : 0;
  const totalSample = snapshots.reduce(
    (a, s) =>
      a +
      Object.values(s.source_breakdown ?? {}).reduce(
        (b, v) => b + (typeof v === "number" ? v : 0),
        0,
      ),
    0,
  );

  if (snapshots.length === 0) {
    return (
      <div
        data-testid="rs-empty-watchlist"
        className="rs-col-card p-10 flex flex-col items-center gap-3 text-center"
        style={{ borderRadius: "12px" }}
      >
        <div className="rs-mono-label">Nothing to monitor yet</div>
        <p
          className="m-0 text-[--color-text-secondary] max-w-[420px]"
          style={{ fontSize: "14px", lineHeight: 1.55 }}
        >
          Add a ticker above or import your portfolio to start tracking retail
          sentiment.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-7" data-testid="overview-all">
      <section
        className="grid gap-6 pb-6 mb-7 border-b animate-rs-section-enter"
        style={{
          gridTemplateColumns: "1.2fr 0.8fr",
          borderColor: "var(--color-border-subtle)",
        }}
      >
        <div className="flex flex-col gap-3.5">
          <span
            className="inline-flex items-center gap-2 font-mono"
            style={{
              fontSize: "10px",
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--color-feedback-success)",
            }}
          >
            <span
              className="inline-block animate-rs-live-pulse"
              style={{
                width: "6px",
                height: "6px",
                borderRadius: "50%",
                background: "var(--color-accent-primary)",
                boxShadow: "0 0 0 4px rgba(212,255,0,0.18)",
              }}
              aria-hidden="true"
            />
            Watchlist · {snapshots.length} tickers
          </span>
          <h1
            className="m-0 text-[--color-text-primary]"
            style={{
              fontSize: "38px",
              fontWeight: 500,
              letterSpacing: "-0.02em",
              lineHeight: 1.05,
            }}
          >
            {meanSentiment > 0.1
              ? "Crowd is leaning long."
              : meanSentiment < -0.1
                ? "Crowd is leaning short."
                : "Crowd is balanced."}{" "}
            <span style={{ color: "var(--color-text-secondary)" }}>
              {spikes.length > 0
                ? `${spikes.length} active buzz spike${spikes.length > 1 ? "s" : ""}.`
                : "No active alerts."}
            </span>
          </h1>
          <div className="grid grid-cols-4 gap-7 pt-1.5">
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Mean sentiment</span>
              <span
                className="rs-mono-value text-[18px]"
                style={{
                  color:
                    meanSentiment > 0
                      ? "var(--color-feedback-success)"
                      : meanSentiment < 0
                        ? "var(--color-feedback-error)"
                        : "var(--color-text-primary)",
                }}
              >
                {meanSentiment >= 0 ? "+" : ""}
                {meanSentiment.toFixed(2)}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Mean buzz</span>
              <span className="rs-mono-value text-[18px]">
                {meanBuzz.toFixed(2)}×
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Sample · 24h</span>
              <span className="rs-mono-value text-[18px]">
                {totalSample.toLocaleString()}
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Active alerts</span>
              <span
                className="rs-mono-value text-[18px]"
                style={{
                  color:
                    spikes.length > 0
                      ? "var(--color-feedback-warning)"
                      : "var(--color-text-primary)",
                }}
              >
                {spikes.length}
              </span>
            </div>
          </div>
        </div>
        <div
          className="rs-col-card p-5 flex flex-col gap-2.5"
          style={{ borderRadius: "12px" }}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="rs-mono-label">Aggregate sentiment</span>
            <span
              className="rs-mono-label"
              style={{ color: "var(--color-feedback-success)" }}
            >
              Live
            </span>
          </div>
          <SentimentGauge score={meanSentiment} />
        </div>
      </section>

      <SectionLabel title="Trending tickers" meta="By buzz × 30d" first />
      <TrendingRail snapshots={snapshots} onPick={onPickTicker} />

      <SectionLabel
        title="Sentiment surface"
        meta="Watchlist × metrics"
      />
      <div
        className="rs-col-card overflow-x-auto"
        style={{ borderRadius: "12px" }}
        data-testid="rs-heatmap"
      >
        <table className="w-full" style={{ borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th
                className="rs-mono-label text-left px-4 py-3"
                style={{
                  borderBottom:
                    "1px solid var(--color-border-subtle)",
                }}
              >
                Ticker
              </th>
              {RS_METRIC_CATALOG.map((m) => (
                <th
                  key={m.id}
                  className="rs-mono-label text-right px-3 py-3 whitespace-nowrap"
                  style={{
                    borderBottom: "1px solid var(--color-border-subtle)",
                  }}
                >
                  {m.label}
                </th>
              ))}
              <th
                className="rs-mono-label text-right px-3 py-3"
                style={{
                  borderBottom: "1px solid var(--color-border-subtle)",
                }}
              >
                Trend
              </th>
            </tr>
          </thead>
          <tbody>
            {snapshots.map((s) => (
              <tr
                key={s.ticker}
                className="cursor-pointer hover:bg-[--color-surface-hover] transition-colors"
                onClick={() => onPickTicker(s.ticker)}
                data-testid={`rs-heat-row-${s.ticker}`}
              >
                <td
                  className="px-4 py-2.5 font-mono font-semibold tracking-[0.02em] text-[--color-text-primary]"
                  style={{
                    fontSize: "13px",
                    borderBottom: "1px solid var(--color-border-subtle)",
                  }}
                >
                  {s.ticker}
                </td>
                {RS_METRIC_CATALOG.map((m) => (
                  <td
                    key={m.id}
                    className="text-right px-3 py-2.5"
                    style={{
                      borderBottom: "1px solid var(--color-border-subtle)",
                    }}
                  >
                    <HeatCell value={metricValue(s, m.field)} field={m.field} />
                  </td>
                ))}
                <td
                  className="px-3 py-2.5"
                  style={{
                    borderBottom: "1px solid var(--color-border-subtle)",
                    minWidth: 80,
                  }}
                >
                  <Spark
                    data={[
                      { x: 0, y: s.sentiment_score - s.sentiment_momentum },
                      { x: 1, y: s.sentiment_score },
                    ]}
                    height={20}
                    tone={s.sentiment_momentum >= 0 ? "accent" : "warn"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
