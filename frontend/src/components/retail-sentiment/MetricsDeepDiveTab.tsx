import { useMemo } from "react";

import type { RsSnapshot } from "../../api/retail-sentiment";
import {
  type MetricDefinition,
  RS_METRIC_CATALOG,
} from "../../lib/retail-sentiment/metric-catalog";
import {
  BullBearStack,
  BuzzBars,
  DivergenceBars,
  MomentumArea,
  SentimentLine,
  Spark,
} from "./charts";
import { ReliabilityBadge } from "./ReliabilityBadge";

interface Props {
  selected: string | null;
  history: RsSnapshot[];
}

const CHART_LABEL: Record<string, string> = {
  gauge: "Arc gauge",
  bar: "Bar chart",
  line: "Line chart",
  area: "Dual-fill area",
  "stacked-bar": "Stacked bar (100%)",
  scatter: "Bubble scatter",
  stat: "Stat card",
};

function metricSeries(history: RsSnapshot[], field: string): Array<{ x: string; y: number }> {
  return [...history]
    .sort((a, b) => a.captured_at.localeCompare(b.captured_at))
    .map((s) => ({
      x: s.captured_at,
      y: (s as unknown as Record<string, number | null>)[field] as number,
    }))
    .filter((p) => p.y !== null && Number.isFinite(p.y));
}

function MetricChart({
  m,
  history,
}: {
  m: MetricDefinition;
  history: RsSnapshot[];
}) {
  const series = useMemo(() => metricSeries(history, m.field), [history, m.field]);

  if (series.length === 0) {
    return (
      <div
        className="rs-mono-label flex items-center justify-center"
        style={{
          height: 120,
          color: "var(--color-text-tertiary)",
          background: "var(--color-bg-code)",
          borderRadius: 6,
        }}
        data-testid={`deep-dive-empty-${m.id}`}
      >
        No history yet
      </div>
    );
  }

  if (m.id === "buzz_volume") return <BuzzBars data={series} />;
  if (m.id === "buzz_sentiment_divergence") return <DivergenceBars data={series} />;
  if (m.id === "sentiment_momentum") return <MomentumArea data={series} />;
  if (m.id === "bull_bear_ratio") {
    const ratioSeries = series.map((p) => {
      const bull = Math.max(0, Math.min(1, p.y));
      return { x: p.x, bull, bear: 1 - bull };
    });
    return <BullBearStack data={ratioSeries} />;
  }
  if (m.chart === "line" || m.chart === "gauge") {
    return <SentimentLine data={series} baseline={0} />;
  }
  if (m.chart === "stat") {
    const tone =
      m.id === "social_velocity" || m.id === "narrative_concentration"
        ? "accent"
        : "cool";
    return <Spark data={series} height={48} tone={tone} ariaLabel={`${m.label} spark`} />;
  }
  return <Spark data={series} height={48} ariaLabel={`${m.label} spark`} />;
}

function MetricLatest({
  m,
  history,
}: {
  m: MetricDefinition;
  history: RsSnapshot[];
}) {
  const sorted = useMemo(
    () =>
      [...history].sort((a, b) => a.captured_at.localeCompare(b.captured_at)),
    [history],
  );
  const latest = sorted.at(-1) ?? null;
  const raw = latest
    ? (latest as unknown as Record<string, number | null>)[m.field]
    : null;
  if (raw === null || raw === undefined || !Number.isFinite(raw)) {
    return (
      <span
        className="rs-mono-value text-[18px]"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        —
      </span>
    );
  }
  const display =
    m.units === "[-1, 1]" || m.units === "[0, 1]" || m.units === "Δ score"
      ? raw.toFixed(2)
      : m.units === "× 30d avg" || m.units === "ratio" || m.units === "stddev"
        ? raw.toFixed(2)
        : m.units === "Δ posts %"
          ? `${(raw * 100).toFixed(0)}%`
          : raw.toFixed(2);
  return (
    <span
      className="rs-mono-value text-[18px]"
      style={{ color: "var(--color-text-primary)" }}
    >
      {display}
    </span>
  );
}

function DeepDiveSection({
  m,
  history,
}: {
  m: MetricDefinition;
  history: RsSnapshot[];
}) {
  return (
    <article
      className="rs-col-card p-6 space-y-4"
      style={{ borderRadius: 12 }}
      data-testid={`deep-dive-${m.id}`}
    >
      <header className="flex items-start gap-4">
        <div
          className="flex items-center justify-center font-mono shrink-0"
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            background: "var(--color-bg-code)",
            color: "var(--color-text-primary)",
            fontSize: 13,
            fontWeight: 600,
          }}
          aria-hidden="true"
        >
          {m.number}
        </div>
        <div className="flex-1 min-w-0">
          <h3
            className="m-0 flex flex-wrap items-center gap-2.5"
            style={{
              fontSize: 16,
              fontWeight: 500,
              color: "var(--color-text-primary)",
              letterSpacing: "-0.005em",
            }}
          >
            {m.label}
            <ReliabilityBadge tier={m.reliability} />
            <span
              className="rs-mono-label"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              pred {m.predictive_strength}/10 · time {m.timeliness}/10
            </span>
          </h3>
          <p
            className="m-0 mt-1.5"
            style={{
              fontSize: 13,
              lineHeight: 1.55,
              color: "var(--color-text-secondary)",
            }}
          >
            {m.description}
          </p>
        </div>
        <div className="flex flex-col items-end gap-0.5 shrink-0">
          <span className="rs-mono-label">Latest</span>
          <MetricLatest m={m} history={history} />
          <span
            className="rs-mono-label"
            style={{ color: "var(--color-text-tertiary)" }}
          >
            {m.units}
          </span>
        </div>
      </header>

      <div
        className="px-3 py-2 font-mono text-[12px] rounded"
        style={{
          background: "var(--color-bg-code)",
          color: "var(--color-text-primary)",
        }}
      >
        <span
          className="rs-mono-label mr-2"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          formula
        </span>
        {m.formula}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between rs-mono-label">
          <span>{CHART_LABEL[m.chart] ?? m.chart}</span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            {history.length} pts
          </span>
        </div>
        <MetricChart m={m} history={history} />
      </div>

      <div
        className="grid gap-4 pt-2 border-t"
        style={{
          gridTemplateColumns: "1fr 1fr",
          borderColor: "var(--color-border-subtle)",
        }}
      >
        <div className="space-y-1">
          <span className="rs-mono-label">What it tells you</span>
          <p
            className="m-0"
            style={{
              fontSize: 12.5,
              lineHeight: 1.55,
              color: "var(--color-text-secondary)",
            }}
          >
            {m.interpretation}
          </p>
        </div>
        <div className="space-y-1">
          <span
            className="rs-mono-label"
            style={{ color: "var(--color-feedback-warning)" }}
          >
            Caveat
          </span>
          <p
            className="m-0"
            style={{
              fontSize: 12.5,
              lineHeight: 1.55,
              color: "var(--color-text-secondary)",
            }}
          >
            {m.caveat}
          </p>
        </div>
      </div>
    </article>
  );
}

export function MetricsDeepDiveTab({ selected, history }: Props) {
  if (!selected) {
    return (
      <div
        className="rs-col-card p-8 text-center"
        style={{ borderRadius: 12 }}
        data-testid="deep-dive-empty-selection"
      >
        <p className="rs-mono-label">Pick a ticker</p>
        <p
          className="m-0 mt-2"
          style={{
            color: "var(--color-text-secondary)",
            fontSize: 13.5,
          }}
        >
          Select a ticker above to see each metric explained against its real
          history. The deep dive renders the same chart shapes the Overview tab
          uses, with formula, latest value, interpretation, and caveat side by
          side.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="deep-dive-tab">
      <header className="flex items-baseline gap-3">
        <h2
          className="m-0"
          style={{
            fontSize: 22,
            fontWeight: 500,
            color: "var(--color-text-primary)",
            letterSpacing: "-0.01em",
          }}
        >
          Metrics Deep Dive
        </h2>
        <span
          className="rs-mono-label"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {selected} · {RS_METRIC_CATALOG.length} metrics
        </span>
      </header>
      <p
        className="m-0 max-w-[760px]"
        style={{
          fontSize: 13.5,
          lineHeight: 1.6,
          color: "var(--color-text-secondary)",
        }}
      >
        Every signal that feeds the dashboard, with the formula, the chart, and
        the practical interpretation. Use this surface to learn how a metric
        behaves before relying on it in your Insights workflow.
      </p>
      <div className="space-y-4 pt-2">
        {RS_METRIC_CATALOG.map((m) => (
          <DeepDiveSection key={m.id} m={m} history={history} />
        ))}
      </div>
    </div>
  );
}
