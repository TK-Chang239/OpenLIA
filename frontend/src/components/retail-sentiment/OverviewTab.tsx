import { useMemo } from "react";

import type { RsQuoteBar, RsSnapshot } from "../../api/retail-sentiment";
import { RS_METRIC_BY_ID } from "../../lib/retail-sentiment/metric-catalog";
import {
  BullBearStack,
  DivergenceBars,
  MomentumArea,
  SentimentPriceOverlay,
} from "./charts";
import { MetricCard } from "./MetricCard";
import { MomentumGauge } from "./MomentumGauge";
import { SentimentGauge } from "./SentimentGauge";

interface Props {
  selected: string;
  snapshot: RsSnapshot;
  history: RsSnapshot[];
  quotes?: RsQuoteBar[];
}

function findOffset(history: RsSnapshot[], days: number): RsSnapshot | null {
  if (history.length === 0) return null;
  const sorted = [...history].sort((a, b) =>
    a.captured_at.localeCompare(b.captured_at),
  );
  const latest = sorted[sorted.length - 1];
  const targetTime = new Date(latest.captured_at).getTime() - days * 86400000;
  let best: RsSnapshot | null = null;
  let bestDelta = Infinity;
  for (const s of sorted) {
    const d = Math.abs(new Date(s.captured_at).getTime() - targetTime);
    if (d < bestDelta) {
      bestDelta = d;
      best = s;
    }
  }
  return best;
}

function formatStat(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return Number(value).toFixed(digits);
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

function HeroStat({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone?: "pos" | "neg" | "warn" | "neutral";
}) {
  const color =
    tone === "pos"
      ? "var(--color-feedback-success)"
      : tone === "neg"
        ? "var(--color-feedback-error)"
        : tone === "warn"
          ? "var(--color-feedback-warning)"
          : "var(--color-text-primary)";
  return (
    <div className="flex flex-col gap-0.5 min-w-0">
      <span className="rs-mono-label">{label}</span>
      <span
        className="rs-mono-value text-[18px]"
        style={{ color }}
      >
        {value}
      </span>
    </div>
  );
}

function HeroSection({
  ticker,
  snap,
  history,
}: {
  ticker: string;
  snap: RsSnapshot;
  history: RsSnapshot[];
}) {
  const prior24 = findOffset(history, 1);
  const prior7 = findOffset(history, 7);
  const delta24 =
    prior24 && prior24.captured_at !== snap.captured_at
      ? snap.sentiment_score - prior24.sentiment_score
      : null;
  const delta7 =
    prior7 && prior7.captured_at !== snap.captured_at
      ? snap.sentiment_score - prior7.sentiment_score
      : null;

  const sourceCount = Object.keys(snap.source_breakdown ?? {}).length;
  const sampleTotal = Object.values(snap.source_breakdown ?? {}).reduce(
    (acc, v) => acc + (typeof v === "number" ? v : 0),
    0,
  );
  const xSourcePct = Number.isFinite(snap.cross_source_agreement)
    ? `${Math.round(snap.cross_source_agreement * 100)}%`
    : "—";
  const bullBear = formatStat(snap.bull_bear_ratio, 2);

  const captured = new Date(snap.captured_at);
  const capturedLabel = captured.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <section
      className="grid gap-6 pb-6 mb-7 border-b animate-rs-section-enter"
      style={{
        gridTemplateColumns: "1.2fr 0.8fr",
        borderColor: "var(--color-border-subtle)",
      }}
      data-testid="rs-hero"
    >
      <div className="flex flex-col gap-3.5 min-w-0">
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
          Retail Sentiment · {ticker} · {capturedLabel}
        </span>
        <h1
          className="text-[--color-text-primary] m-0"
          style={{
            fontSize: "38px",
            fontWeight: 500,
            letterSpacing: "-0.02em",
            lineHeight: 1.05,
          }}
        >
          {ticker}{" "}
          <span style={{ color: "var(--color-text-secondary)" }}>
            · {snap.sentiment_score >= 0 ? "Crowd is leaning long" : "Crowd is leaning short"}
          </span>
        </h1>
        <p
          className="m-0 max-w-[600px]"
          style={{
            fontSize: "15px",
            color: "var(--color-text-secondary)",
            lineHeight: 1.6,
          }}
        >
          {snap.narrative ?? (
            <span className="text-[--color-text-tertiary]">
              No narrative synthesized yet — a Quick-tier model is required for
              automated takes. The metrics below are still live.
            </span>
          )}
        </p>
        <div className="grid grid-cols-4 gap-7 pt-1.5">
          <HeroStat label="Bull / Bear" value={bullBear} />
          <HeroStat
            label="Buzz × 30d"
            value={formatStat(snap.buzz_volume, 2)}
            tone={snap.buzz_volume > 1.5 ? "warn" : "neutral"}
          />
          <HeroStat label="Sources" value={`${sourceCount}`} />
          <HeroStat label="X-source agree" value={xSourcePct} />
        </div>
      </div>

      <div
        className="rs-col-card p-5 flex flex-col gap-2.5"
        style={{ borderRadius: "12px" }}
      >
        <div className="flex items-center justify-between gap-3">
          <span className="rs-mono-label">Sentiment Index</span>
          <span
            className="rs-mono-label"
            style={{ color: "var(--color-feedback-success)" }}
          >
            Live
          </span>
        </div>
        <SentimentGauge
          score={snap.sentiment_score}
          delta24h={delta24}
          delta7d={delta7}
        />
        <div
          className="rs-mono-label pt-3 border-t flex items-center justify-between"
          style={{ borderColor: "var(--color-border-subtle)" }}
        >
          <span>Sample · {sampleTotal.toLocaleString()}</span>
          <span>Captured · {captured.toLocaleTimeString()}</span>
        </div>
      </div>
    </section>
  );
}

function LiaTakeCard({ snap }: { snap: RsSnapshot }) {
  const sourceCount = Object.keys(snap.source_breakdown ?? {}).length;
  const sample = Object.values(snap.source_breakdown ?? {}).reduce(
    (a, v) => a + (typeof v === "number" ? v : 0),
    0,
  );
  const confidence = Number.isFinite(snap.cross_source_agreement)
    ? Math.round(snap.cross_source_agreement * 100)
    : null;

  return (
    <article
      className="grid gap-5 rs-col-card p-6 animate-rs-section-enter"
      style={{ gridTemplateColumns: "56px 1fr", borderRadius: "12px" }}
    >
      <div
        className="self-start flex items-center justify-center"
        style={{
          width: 44,
          height: 44,
          borderRadius: 8,
          background: "var(--color-accent-primary)",
          color: "var(--color-accent-on)",
          fontFamily: "var(--font-mono, monospace)",
          fontSize: 12,
          fontWeight: 700,
          boxShadow: "0 0 14px rgba(212,255,0,0.35)",
        }}
        aria-hidden="true"
      >
        LIA
      </div>
      <div className="flex flex-col gap-3 min-w-0">
        <div className="rs-mono-label flex items-center gap-2.5 flex-wrap">
          <span>Retail Sentiment</span>
          <span
            aria-hidden="true"
            style={{
              width: 3,
              height: 3,
              background: "var(--color-text-tertiary)",
              borderRadius: "50%",
            }}
          />
          <span>
            Confidence {confidence !== null ? `${confidence} / 100` : "—"}
          </span>
          <span
            aria-hidden="true"
            style={{
              width: 3,
              height: 3,
              background: "var(--color-text-tertiary)",
              borderRadius: "50%",
            }}
          />
          <span>Sources · {sourceCount}</span>
          <span
            aria-hidden="true"
            style={{
              width: 3,
              height: 3,
              background: "var(--color-text-tertiary)",
              borderRadius: "50%",
            }}
          />
          <span>Sample · {sample.toLocaleString()}</span>
        </div>
        <p
          className="m-0"
          style={{
            fontSize: "14.5px",
            lineHeight: 1.65,
            color: "var(--color-text-secondary)",
          }}
          data-testid="rs-lia-take"
        >
          {snap.narrative ?? (
            <span className="text-[--color-text-tertiary]">
              No narrative synthesis yet for this snapshot. Run a fresh snapshot
              with a Quick-tier model configured to populate the LIA take.
            </span>
          )}
        </p>
      </div>
    </article>
  );
}

function CompactTier({ snap }: { snap: RsSnapshot }) {
  const tile = (key: keyof RsSnapshot, label?: string) => {
    const meta = RS_METRIC_BY_ID[String(key)];
    const raw = snap[key] as number | null;
    const disabled =
      raw === null || raw === undefined || !Number.isFinite(raw as number);
    return (
      <MetricCard
        key={String(key)}
        label={label ?? meta?.label ?? String(key)}
        value={disabled ? null : (raw as number)}
        units={meta?.units}
        reliability={meta?.reliability}
        disabledNote={
          disabled
            ? `Awaiting ${meta?.label ?? key} — provider may not be configured.`
            : undefined
        }
      />
    );
  };

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3" data-testid="rs-compact-tier">
      {tile("buzz_volume")}
      {tile("bull_bear_ratio")}
      {tile("social_velocity")}
      {tile("buzz_sentiment_divergence")}
      {tile("put_call_ratio")}
      {tile("short_interest_pressure")}
      {tile("narrative_concentration")}
      {tile("institutional_retail_gap")}
    </div>
  );
}

function MomentumPanel({
  snap,
  history,
}: {
  snap: RsSnapshot;
  history: RsSnapshot[];
}) {
  const series = useMemo(
    () =>
      [...history]
        .sort((a, b) => a.captured_at.localeCompare(b.captured_at))
        .map((s) => ({ x: s.captured_at, y: s.sentiment_momentum })),
    [history],
  );
  return (
    <div
      className="rs-col-card grid gap-4 p-5"
      style={{ gridTemplateColumns: "240px 1fr", alignItems: "center" }}
    >
      <MomentumGauge momentum={snap.sentiment_momentum} />
      <div className="min-w-0">
        <div className="rs-mono-label mb-2">5d Momentum trend</div>
        <MomentumArea data={series} />
      </div>
    </div>
  );
}

function ChartsGrid({
  snap,
  history,
  quotes,
}: {
  snap: RsSnapshot;
  history: RsSnapshot[];
  quotes: RsQuoteBar[];
}) {
  const sortedHistory = useMemo(
    () =>
      [...history].sort((a, b) => a.captured_at.localeCompare(b.captured_at)),
    [history],
  );
  const sentimentSeries = sortedHistory.map((s) => ({
    x: s.captured_at.slice(0, 10),
    y: s.sentiment_score,
  }));
  const buzzSeries = sortedHistory.map((s) => ({
    x: s.captured_at.slice(0, 10),
    y: s.buzz_volume,
  }));
  const divergenceSeries = sortedHistory.map((s) => ({
    x: s.captured_at,
    y: s.buzz_sentiment_divergence,
  }));
  const ratioSeries = sortedHistory.map((s) => {
    const bull = Math.max(0, Math.min(1, s.bull_bear_ratio));
    return { x: s.captured_at, bull, bear: 1 - bull };
  });

  // Align price bars to sentiment dates so the overlay shares a single x-axis.
  const sortedQuotes = useMemo(
    () => [...quotes].sort((a, b) => a.date.localeCompare(b.date)),
    [quotes],
  );
  const quotesByDate = new Map(sortedQuotes.map((q) => [q.date, q]));
  const priceSeries = sentimentSeries.map((s) => {
    const q = quotesByDate.get(s.x);
    return { x: s.x, y: q ? q.cumulative_pct : Number.NaN };
  });
  const priceHasData = priceSeries.some((p) => Number.isFinite(p.y));
  const priceWindowPct = priceHasData
    ? sortedQuotes.at(-1)?.cumulative_pct ?? 0
    : 0;

  return (
    <div className="grid grid-cols-1 gap-4">
      <div className="rs-col-card p-5">
        <div className="flex items-center justify-between rs-mono-label mb-2">
          <span>Sentiment vs price · {sortedHistory.length}d window</span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            {priceHasData
              ? `price ${priceWindowPct >= 0 ? "+" : ""}${priceWindowPct.toFixed(2)}%`
              : "price overlay awaiting EODHD key"}
          </span>
        </div>
        <SentimentPriceOverlay
          sentiment={sentimentSeries}
          priceCumulativePct={priceSeries}
          buzz={buzzSeries}
        />
        <div className="text-[11px] mt-2 flex flex-wrap gap-3 rs-mono-label">
          <span style={{ color: "var(--color-feedback-success)" }}>
            ─ sentiment (left axis)
          </span>
          <span style={{ color: "var(--color-text-primary)" }}>
            ┄ price cumulative % (right axis)
          </span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            ▮ buzz × 30d (background)
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rs-col-card p-5">
          <div className="flex items-center justify-between rs-mono-label mb-2">
            <span>Bull / Bear stack</span>
            <span>latest · {formatStat(snap.bull_bear_ratio)}</span>
          </div>
          <BullBearStack data={ratioSeries} />
        </div>
        <div className="rs-col-card p-5">
          <div className="flex items-center justify-between rs-mono-label mb-2">
            <span>Buzz / sentiment divergence</span>
            <span>thresholds ±1.0</span>
          </div>
          <DivergenceBars data={divergenceSeries} />
        </div>
      </div>
    </div>
  );
}

export function OverviewTab({
  selected,
  snapshot,
  history,
  quotes = [],
}: Props) {
  return (
    <div className="space-y-7" data-testid="overview-single">
      <HeroSection ticker={selected} snap={snapshot} history={history} />

      <SectionLabel title="Today's read" meta="LIA narrative" first />
      <LiaTakeCard snap={snapshot} />

      <SectionLabel title="Momentum" meta="last 7 snapshots" />
      <MomentumPanel snap={snapshot} history={history} />

      <SectionLabel title="Metrics" meta="Compact tier · 8" />
      <CompactTier snap={snapshot} />

      <SectionLabel title="Time series" meta="all available history" />
      <ChartsGrid snap={snapshot} history={history} quotes={quotes} />
    </div>
  );
}
