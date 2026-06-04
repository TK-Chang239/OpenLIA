import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getDashboard,
  refreshDashboard,
  type RetailSentimentPayload,
} from "../../../api/retail-sentiment";
import { MetricCard } from "../../../components/retail-sentiment/MetricCard";
import { MomentumGauge } from "../../../components/retail-sentiment/MomentumGauge";
import { SentimentGauge } from "../../../components/retail-sentiment/SentimentGauge";

const POLL_INTERVAL_MS = 6000;
const POLL_MAX_ATTEMPTS = 70;

// ---------------------------------------------------------------------------
// Small local UI helpers
// ---------------------------------------------------------------------------

function SectionLabel({
  children,
  meta,
  first,
}: {
  children: React.ReactNode;
  meta?: string;
  first?: boolean;
}) {
  return (
    <div className={`rs-sec-label${first ? " first" : ""}`}>
      <span>{children}</span>
      <span className="rs-rule" aria-hidden="true" />
      {meta ? <span>{meta}</span> : null}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div
      className="space-y-4 animate-pulse"
      data-testid="rs-overview-loading"
      aria-live="polite"
      aria-label="Generating dashboard — please wait"
    >
      {[...Array(4)].map((_, i) => (
        <div
          key={i}
          className="h-20 rounded-xl bg-[--color-bg-elevated]"
          style={{ opacity: 0.6 - i * 0.1 }}
        />
      ))}
    </div>
  );
}

function EmptyState({
  ticker,
  onGenerate,
  generating,
  note,
}: {
  ticker: string;
  onGenerate: () => void;
  generating: boolean;
  note: string | null;
}) {
  return (
    <div
      className="rs-col-card p-10 text-center space-y-4"
      style={{ borderRadius: 12 }}
      data-testid="rs-overview-empty"
    >
      <p
        className="font-mono text-[11px] uppercase tracking-[0.14em] text-[--color-text-tertiary]"
      >
        Retail Sentiment · {ticker}
      </p>
      <p className="text-[15px] text-[--color-text-secondary]">
        No dashboard yet for {ticker}. Generate a live reading from current web and news data.
      </p>
      {note ? (
        <p
          className="text-[13px] text-[--color-feedback-warning]"
          data-testid="rs-generate-note"
        >
          {note}
        </p>
      ) : null}
      <button
        type="button"
        data-testid="rs-generate-now"
        disabled={generating}
        onClick={onGenerate}
        className="inline-flex items-center gap-2 rounded-md border border-[--color-accent-primary] bg-[--color-accent-primary] px-4 py-2 text-[13px] font-medium text-[--color-accent-on] hover:opacity-90 disabled:opacity-60"
      >
        {generating ? "Generating…" : "Generate now"}
      </button>
    </div>
  );
}

function StaleBadge() {
  return (
    <span
      className="inline-flex items-center rounded-full border border-[--color-feedback-warning] px-2.5 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-feedback-warning]"
      data-testid="rs-stale-badge"
    >
      Stale
    </span>
  );
}

// ---------------------------------------------------------------------------
// Payload sections
// ---------------------------------------------------------------------------

function SignalRow({
  signal,
}: {
  signal: RetailSentimentPayload["signals"][number];
}) {
  const color =
    signal.severity === "alert"
      ? "var(--color-feedback-error)"
      : signal.severity === "caution"
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  const label =
    signal.severity === "alert"
      ? "ALERT"
      : signal.severity === "caution"
        ? "CAUTION"
        : "INFO";

  return (
    <li
      data-testid={`rs-signal-${signal.severity}`}
      className="flex items-start gap-3 py-2.5 border-b last:border-0"
      style={{ borderColor: "var(--color-border-subtle)" }}
    >
      <span
        className="mt-0.5 shrink-0 font-mono text-[9px] uppercase tracking-[0.12em]"
        style={{ color }}
      >
        {label}
      </span>
      <div className="min-w-0 space-y-0.5">
        <div className="text-[13px] font-medium text-[--color-text-primary]">
          {signal.name}
        </div>
        <div className="text-[12.5px] text-[--color-text-secondary]">{signal.note}</div>
      </div>
    </li>
  );
}

function EvidenceRow({
  item,
}: {
  item: RetailSentimentPayload["evidence"][number];
}) {
  const color =
    item.classification === "bullish"
      ? "var(--color-feedback-success)"
      : item.classification === "bearish"
        ? "var(--color-feedback-error)"
        : "var(--color-text-tertiary)";

  return (
    <li
      data-testid="rs-evidence-item"
      className="flex items-start gap-3 py-2.5 border-b last:border-0"
      style={{ borderColor: "var(--color-border-subtle)" }}
    >
      <span
        className="mt-0.5 shrink-0 font-mono text-[9px] uppercase tracking-[0.12em]"
        style={{ color, minWidth: 50 }}
      >
        {item.classification}
      </span>
      <div className="min-w-0 flex-1 space-y-0.5">
        <div className="text-[13px] text-[--color-text-primary]">
          {item.url ? (
            <a
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
              className="hover:underline"
            >
              {item.title}
            </a>
          ) : (
            item.title
          )}
        </div>
        <div className="text-[11.5px] text-[--color-text-tertiary]">
          {item.source}
          {item.published_at ? ` · ${new Date(item.published_at).toLocaleDateString()}` : ""}
        </div>
      </div>
    </li>
  );
}

function PayloadView({
  ticker,
  payload,
  generatedAt,
  isStale,
  onGenerate,
  generating,
  note,
}: {
  ticker: string;
  payload: RetailSentimentPayload;
  generatedAt: string | null;
  isStale: boolean;
  onGenerate: () => void;
  generating: boolean;
  note: string | null;
}) {
  const { t } = useTranslation();
  const capturedLabel = payload.captured_at
    ? new Date(payload.captured_at).toLocaleString()
    : generatedAt
      ? new Date(generatedAt).toLocaleString()
      : "—";

  const directionColor =
    payload.direction === "bullish"
      ? "var(--color-feedback-success)"
      : payload.direction === "bearish"
        ? "var(--color-feedback-error)"
        : "var(--color-text-secondary)";

  const buzzColor =
    payload.buzz_level === "high"
      ? "var(--color-feedback-error)"
      : payload.buzz_level === "elevated"
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";

  return (
    <article className="space-y-7" data-testid="rs-overview-payload">
      {/* Hero */}
      <section
        className="grid gap-6"
        style={{ gridTemplateColumns: "1.2fr 0.8fr" }}
        data-testid="rs-hero"
      >
        <div className="flex flex-col gap-3 min-w-0">
          <span
            className="font-mono text-[10px] uppercase tracking-[0.14em]"
            style={{ color: "var(--color-feedback-success)" }}
          >
            Retail Sentiment · {ticker} · {capturedLabel}
          </span>
          <h1
            className="m-0 text-[--color-text-primary]"
            style={{
              fontSize: 36,
              fontWeight: 500,
              letterSpacing: "-0.02em",
              lineHeight: 1.05,
            }}
          >
            {ticker}{" "}
            <span style={{ color: directionColor }}>
              · {payload.direction.charAt(0).toUpperCase() + payload.direction.slice(1)}
            </span>
          </h1>
          <p
            className="m-0 max-w-[600px] text-[--color-text-secondary]"
            style={{ fontSize: 14.5, lineHeight: 1.65 }}
            data-testid="rs-narrative"
          >
            {payload.narrative}
          </p>
          <div className="flex items-center gap-4 pt-1">
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Bull</span>
              <span
                className="rs-mono-value text-[18px]"
                style={{ color: "var(--color-feedback-success)" }}
                data-testid="rs-bull-pct"
              >
                {payload.bull_pct.toFixed(1)}%
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Bear</span>
              <span
                className="rs-mono-value text-[18px]"
                style={{ color: "var(--color-feedback-error)" }}
                data-testid="rs-bear-pct"
              >
                {payload.bear_pct.toFixed(1)}%
              </span>
            </div>
            <div className="flex flex-col gap-0.5">
              <span className="rs-mono-label">Buzz</span>
              <span
                className="rs-mono-value text-[18px]"
                style={{ color: buzzColor }}
                data-testid="rs-buzz-level"
              >
                {payload.buzz_level.charAt(0).toUpperCase() + payload.buzz_level.slice(1)}
              </span>
            </div>
          </div>
        </div>

        <div
          className="rs-col-card p-5 flex flex-col gap-2.5"
          style={{ borderRadius: 12 }}
        >
          <div className="flex items-center justify-between gap-3">
            <span className="rs-mono-label">
              {t("retail_sentiment.overview.sentiment_index")}
            </span>
            <div className="flex items-center gap-2">
              {isStale ? <StaleBadge /> : null}
              <button
                type="button"
                data-testid="rs-generate-now"
                disabled={generating}
                onClick={onGenerate}
                className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[--color-border-subtle] bg-transparent px-3 font-mono text-[11px] text-[--color-text-secondary] hover:border-[--color-accent-primary] hover:text-[--color-text-primary] disabled:opacity-50"
              >
                {generating ? "Generating…" : "Generate now"}
              </button>
            </div>
          </div>
          <SentimentGauge score={payload.sentiment_score} scale="signed" />
          {note ? (
            <p
              className="text-[12px] text-[--color-feedback-warning]"
              data-testid="rs-generate-note"
            >
              {note}
            </p>
          ) : null}
        </div>
      </section>

      {/* Buzz note */}
      <div
        className="rs-col-card px-5 py-3 text-[13px] text-[--color-text-secondary]"
        style={{ borderRadius: 10, borderLeft: `3px solid ${buzzColor}` }}
        data-testid="rs-buzz-note"
      >
        <span className="font-medium text-[--color-text-primary]" style={{ color: buzzColor }}>
          Buzz · {payload.buzz_level.toUpperCase()}
        </span>{" "}
        — {payload.buzz_note}
      </div>

      {/* Momentum */}
      <SectionLabel meta={payload.trend_label ?? undefined}>Momentum</SectionLabel>
      <div
        className="rs-col-card p-5"
        style={{ gridTemplateColumns: "240px 1fr" }}
      >
        {payload.momentum !== null ? (
          <div className="flex items-center gap-6">
            <MomentumGauge momentum={payload.momentum} />
            {payload.trend_label ? (
              <p className="text-[13.5px] text-[--color-text-secondary]" data-testid="rs-trend-label">
                {payload.trend_label}
              </p>
            ) : null}
          </div>
        ) : (
          <div className="py-4 text-center text-[13px] text-[--color-text-tertiary]" data-testid="rs-momentum-building">
            Building history — momentum available after multiple readings.
          </div>
        )}
      </div>

      {/* Narratives */}
      {payload.narratives.length > 0 ? (
        <>
          <SectionLabel meta={`${payload.narratives.length} themes`}>Narratives</SectionLabel>
          <ul
            className="rs-col-card divide-y"
            style={{ borderRadius: 10, ["--tw-divide-opacity" as string]: 1 }}
            data-testid="rs-narratives"
          >
            {payload.narratives.map((n, i) => (
              <li
                key={i}
                className="px-5 py-3 text-[13.5px] text-[--color-text-secondary]"
              >
                {n}
              </li>
            ))}
          </ul>
        </>
      ) : null}

      {/* Signals */}
      {payload.signals.length > 0 ? (
        <>
          <SectionLabel meta={`${payload.signals.length} signals`}>Signals</SectionLabel>
          <ul
            className="rs-col-card px-5"
            style={{ borderRadius: 10 }}
            data-testid="rs-signals"
          >
            {payload.signals.map((s, i) => (
              <SignalRow key={i} signal={s} />
            ))}
          </ul>
        </>
      ) : null}

      {/* Optional tiles */}
      {(payload.aggregated_sentiment !== null || payload.analyst_gap !== null) ? (
        <>
          <SectionLabel>Data crosscheck</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {payload.aggregated_sentiment !== null ? (
              <MetricCard
                label="Aggregated sentiment"
                value={payload.aggregated_sentiment}
                units="[-1,1]"
                digits={3}
                data-testid="rs-aggregated-sentiment"
              />
            ) : null}
            {payload.analyst_gap !== null ? (
              <MetricCard
                label="Analyst gap"
                value={payload.analyst_gap}
                digits={3}
                data-testid="rs-analyst-gap"
              />
            ) : null}
          </div>
        </>
      ) : null}

      {/* Evidence */}
      {payload.evidence.length > 0 ? (
        <>
          <SectionLabel meta={`${payload.evidence.length} items`}>Evidence</SectionLabel>
          <ul
            className="rs-col-card px-5"
            style={{ borderRadius: 10 }}
            data-testid="rs-evidence"
          >
            {payload.evidence.map((item, i) => (
              <EvidenceRow key={i} item={item} />
            ))}
          </ul>
        </>
      ) : null}
    </article>
  );
}

// ---------------------------------------------------------------------------
// Main exported component
// ---------------------------------------------------------------------------

export default function RsOverviewView({ ticker }: { ticker: string }) {
  const [payload, setPayload] = useState<RetailSentimentPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [generatedAt, setGeneratedAt] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (pollRef.current !== null) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  const load = () => {
    setLoading(true);
    getDashboard(ticker)
      .then((r) => {
        setPayload(r.payload);
        setGeneratedAt(r.generated_at);
        setIsStale(r.is_stale);
      })
      .catch(() => setPayload(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    return stopPolling;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]);

  const startPolling = (priorGeneratedAt: string | null) => {
    stopPolling();
    let attempts = 0;
    pollRef.current = setInterval(() => {
      attempts += 1;
      getDashboard(ticker)
        .then((r) => {
          // A new result arrived when generated_at advances.
          if (r.payload && r.generated_at !== priorGeneratedAt) {
            stopPolling();
            setPayload(r.payload);
            setGeneratedAt(r.generated_at);
            setIsStale(r.is_stale);
            setGenerating(false);
            setNote(null);
          } else if (attempts >= POLL_MAX_ATTEMPTS) {
            stopPolling();
            setGenerating(false);
            setNote("Still generating. Reload in a moment to see the result.");
          }
        })
        .catch(() => undefined);
    }, POLL_INTERVAL_MS);
  };

  const onGenerate = () => {
    setNote(
      "Generating a live reading — this can take a few minutes. Keep this tab open.",
    );
    setGenerating(true);
    const prevGeneratedAt = generatedAt;
    refreshDashboard(ticker)
      .then((r) => {
        if (r.status === "queued" || r.status === "already_running") {
          if (r.status === "already_running") {
            setNote("A reading is already being generated — watching for the result.");
          }
          startPolling(prevGeneratedAt);
        } else {
          setGenerating(false);
          setNote("Generation could not start (background scheduler unavailable).");
        }
      })
      .catch(() => {
        setGenerating(false);
        setNote("Could not start generation. Please try again.");
      });
  };

  if (loading) return <LoadingSkeleton />;

  if (!payload) {
    return (
      <EmptyState
        ticker={ticker}
        onGenerate={onGenerate}
        generating={generating}
        note={note}
      />
    );
  }

  return (
    <PayloadView
      ticker={ticker}
      payload={payload}
      generatedAt={generatedAt}
      isStale={isStale}
      onGenerate={onGenerate}
      generating={generating}
      note={note}
    />
  );
}
