import { useMemo } from "react";
import { useTranslation } from "react-i18next";

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

const CHART_LABEL_KEY: Record<string, string> = {
  gauge: "retail_sentiment.deep_dive.chart_gauge",
  bar: "retail_sentiment.deep_dive.chart_bar",
  line: "retail_sentiment.deep_dive.chart_line",
  area: "retail_sentiment.deep_dive.chart_area",
  "stacked-bar": "retail_sentiment.deep_dive.chart_stacked",
  scatter: "retail_sentiment.deep_dive.chart_scatter",
  stat: "retail_sentiment.deep_dive.chart_stat",
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
  t,
}: {
  m: MetricDefinition;
  history: RsSnapshot[];
  t: (key: string) => string;
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
        {t("retail_sentiment.deep_dive.empty_history")}
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
  t,
}: {
  m: MetricDefinition;
  history: RsSnapshot[];
  t: (key: string, opts?: Record<string, unknown>) => string;
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
              {t("retail_sentiment.deep_dive.pred_time", {
                pred: m.predictive_strength,
                time: m.timeliness,
              })}
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
          <span className="rs-mono-label">
            {t("retail_sentiment.deep_dive.latest")}
          </span>
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
          {t("retail_sentiment.deep_dive.formula")}
        </span>
        {m.formula}
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between rs-mono-label">
          <span>
            {CHART_LABEL_KEY[m.chart] ? t(CHART_LABEL_KEY[m.chart]) : m.chart}
          </span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            {t("retail_sentiment.deep_dive.pts_suffix", {
              count: history.length,
            })}
          </span>
        </div>
        <MetricChart m={m} history={history} t={t} />
      </div>

      <div
        className="grid gap-4 pt-2 border-t"
        style={{
          gridTemplateColumns: "1fr 1fr",
          borderColor: "var(--color-border-subtle)",
        }}
      >
        <div className="space-y-1">
          <span className="rs-mono-label">
            {t("retail_sentiment.deep_dive.what_it_tells")}
          </span>
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
            {t("retail_sentiment.deep_dive.caveat")}
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
  const { t } = useTranslation();
  if (!selected) {
    return (
      <div
        className="rs-col-card p-8 text-center"
        style={{ borderRadius: 12 }}
        data-testid="deep-dive-empty-selection"
      >
        <p className="rs-mono-label">
          {t("retail_sentiment.deep_dive.select_hint_title")}
        </p>
        <p
          className="m-0 mt-2"
          style={{
            color: "var(--color-text-secondary)",
            fontSize: 13.5,
          }}
        >
          {t("retail_sentiment.deep_dive.select_hint_body")}
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
          {t("retail_sentiment.deep_dive.title")}
        </h2>
        <span
          className="rs-mono-label"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {t("retail_sentiment.deep_dive.ticker_metrics", {
            ticker: selected,
            count: RS_METRIC_CATALOG.length,
          })}
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
        {t("retail_sentiment.deep_dive.intro")}
      </p>
      <div className="space-y-4 pt-2">
        {RS_METRIC_CATALOG.map((m) => (
          <DeepDiveSection key={m.id} m={m} history={history} t={t} />
        ))}
      </div>
    </div>
  );
}
