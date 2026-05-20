import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import type { RsSnapshot, RsSpike } from "../../api/retail-sentiment";
import {
  FRAMEWORK_QUESTIONS,
  RS_METRIC_CATALOG,
  type FrameworkQuestion,
  type MetricDefinition,
} from "../../lib/retail-sentiment/metric-catalog";
import { ReliabilityScatter } from "./charts";
import { SignalAlert } from "./SignalAlert";

interface Props {
  selected: string | null;
  snapshots: RsSnapshot[];
  spikes: RsSpike[];
  onPickTicker?: (ticker: string) => void;
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

function metricValue(
  s: RsSnapshot | null,
  field: string,
): number | null {
  if (!s) return null;
  const v = (s as unknown as Record<string, number | null>)[field];
  return v === null || v === undefined || !Number.isFinite(v as number)
    ? null
    : (v as number);
}

function MetricSnapshotChip({
  m,
  value,
  t,
}: {
  m: MetricDefinition;
  value: number | null;
  t: (key: string) => string;
}) {
  let answer = "—";
  let tone = "var(--color-text-secondary)";

  if (value === null) {
    answer = t("retail_sentiment.insights.awaiting_data");
    tone = "var(--color-text-tertiary)";
  } else if (m.id === "sentiment_score") {
    answer =
      value >= 0.1
        ? t("retail_sentiment.insights.bullish")
        : value <= -0.1
          ? t("retail_sentiment.insights.bearish")
          : t("retail_sentiment.insights.balanced");
    tone =
      value >= 0.1
        ? "var(--color-feedback-success)"
        : value <= -0.1
          ? "var(--color-feedback-error)"
          : "var(--color-text-secondary)";
  } else if (m.id === "buzz_volume") {
    answer =
      value > 1.5
        ? t("retail_sentiment.insights.spike")
        : value > 1.0
          ? t("retail_sentiment.insights.elevated")
          : t("retail_sentiment.insights.normal");
    tone =
      value > 1.5
        ? "var(--color-feedback-error)"
        : value > 1.0
          ? "var(--color-feedback-warning)"
          : "var(--color-text-secondary)";
  } else if (m.id === "sentiment_momentum") {
    answer =
      value > 0.02
        ? t("retail_sentiment.insights.improving")
        : value < -0.02
          ? t("retail_sentiment.insights.deteriorating")
          : t("retail_sentiment.insights.flat");
    tone =
      value > 0.02
        ? "var(--color-feedback-success)"
        : value < -0.02
          ? "var(--color-feedback-error)"
          : "var(--color-text-secondary)";
  } else if (m.id === "bull_bear_ratio") {
    answer =
      value > 0.7
        ? t("retail_sentiment.insights.crowded_long")
        : value < 0.3
          ? t("retail_sentiment.insights.crowded_short")
          : t("retail_sentiment.insights.mixed");
    tone =
      value > 0.7 || value < 0.3
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  } else if (m.id === "buzz_sentiment_divergence") {
    answer =
      value > 1
        ? t("retail_sentiment.insights.panic")
        : value < -1
          ? t("retail_sentiment.insights.stealth_bid")
          : t("retail_sentiment.insights.no_edge");
    tone =
      value > 1
        ? "var(--color-feedback-error)"
        : value < -1
          ? "var(--color-feedback-success)"
          : "var(--color-text-secondary)";
  } else if (m.id === "social_velocity") {
    answer =
      value > 1
        ? t("retail_sentiment.insights.accelerating")
        : value < -0.5
          ? t("retail_sentiment.insights.decelerating")
          : t("retail_sentiment.insights.steady");
    tone =
      value > 1
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  } else if (m.id === "cross_source_agreement") {
    answer =
      value > 0.7
        ? t("retail_sentiment.insights.high")
        : value > 0.4
          ? t("retail_sentiment.insights.mixed")
          : t("retail_sentiment.insights.low");
    tone =
      value > 0.7
        ? "var(--color-feedback-success)"
        : value > 0.4
          ? "var(--color-feedback-warning)"
          : "var(--color-feedback-error)";
  } else {
    answer = value.toFixed(2);
  }

  return (
    <div className="rs-col-card p-4 flex flex-col gap-1.5" style={{ borderRadius: "10px" }}>
      <div className="flex items-center justify-between gap-2">
        <span className="rs-mono-label truncate">{m.label}</span>
        <span
          className="rs-mono-value text-[11px]"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          {value === null ? "—" : value.toFixed(2)}
          {m.units !== "ratio" && m.units !== "[-1, 1]" && m.units !== "[0, 1]"
            ? ` ${m.units}`
            : ""}
        </span>
      </div>
      <div
        className="rs-mono-value font-medium"
        style={{ fontSize: "16px", color: tone }}
      >
        {answer}
      </div>
      <p
        className="m-0"
        style={{
          fontSize: "12.5px",
          lineHeight: 1.5,
          color: "var(--color-text-secondary)",
        }}
      >
        {m.interpretation}
      </p>
    </div>
  );
}

function FrameworkSection({
  question,
  metrics,
  snap,
  t,
}: {
  question: FrameworkQuestion;
  metrics: MetricDefinition[];
  snap: RsSnapshot | null;
  t: (key: string) => string;
}) {
  if (metrics.length === 0) return null;
  return (
    <section
      className="space-y-3"
      data-testid={`rs-framework-${question}`}
    >
      <h3
        className="m-0 text-[--color-text-primary]"
        style={{
          fontSize: "16px",
          fontWeight: 500,
          letterSpacing: "-0.01em",
        }}
      >
        {FRAMEWORK_QUESTIONS[question]}
      </h3>
      <div className="grid gap-3 md:grid-cols-2">
        {metrics.map((m) => (
          <MetricSnapshotChip
            key={m.id}
            m={m}
            value={metricValue(snap, m.field)}
            t={t}
          />
        ))}
      </div>
    </section>
  );
}

function NarrativeCard({
  snap,
  t,
}: {
  snap: RsSnapshot;
  t: (key: string) => string;
}) {
  return (
    <article
      className="grid gap-5 rs-col-card p-6"
      style={{ gridTemplateColumns: "56px 1fr", borderRadius: "12px" }}
      data-testid="rs-narrative-card"
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
        }}
        aria-hidden="true"
      >
        LIA
      </div>
      <div className="flex flex-col gap-2 min-w-0">
        <span className="rs-mono-label">
          {t("retail_sentiment.insights.narrative_synthesis")}
        </span>
        <p
          className="m-0"
          style={{
            fontSize: "14px",
            lineHeight: 1.65,
            color: "var(--color-text-primary)",
          }}
          data-testid="narrative-paragraph"
        >
          {snap.narrative ?? (
            <span style={{ color: "var(--color-text-tertiary)" }}>
              {t("retail_sentiment.insights.no_synthesis")}
            </span>
          )}
        </p>
      </div>
    </article>
  );
}

export function InsightsTab({
  selected,
  snapshots,
  spikes,
  onPickTicker,
}: Props) {
  const { t } = useTranslation();
  const snap = selected
    ? snapshots.find((s) => s.ticker === selected) ?? null
    : null;
  const visibleSpikes = useMemo(
    () =>
      selected ? spikes.filter((sp) => sp.ticker === selected) : spikes,
    [selected, spikes],
  );

  const reliabilityRows = RS_METRIC_CATALOG.map((m) => ({
    id: m.id,
    label: m.label,
    predictive_strength: m.predictive_strength,
    timeliness: m.timeliness,
    data_volume:
      snapshots.reduce((acc, s) => {
        const v = (s as unknown as Record<string, number | null>)[m.field];
        return acc + (v === null || v === undefined || !Number.isFinite(v as number) ? 0 : 1);
      }, 0) || 1,
    has_data: snapshots.some((s) => {
      const v = (s as unknown as Record<string, number | null>)[m.field];
      return v !== null && v !== undefined && Number.isFinite(v as number);
    }),
  }));

  const grouped: Record<FrameworkQuestion, MetricDefinition[]> = {
    mood: [],
    attention: [],
    direction: [],
    conviction: [],
    contrarian: [],
    trust: [],
  };
  for (const m of RS_METRIC_CATALOG) {
    if (m.framework) grouped[m.framework].push(m);
  }

  return (
    <div className="space-y-7">
      <SectionLabel
        title={t("retail_sentiment.insights.active_signals")}
        meta={t("retail_sentiment.insights.alerts_count", {
          count: visibleSpikes.length,
        })}
        first
      />
      {visibleSpikes.length === 0 ? (
        <div
          className="rs-col-card p-5"
          style={{ borderRadius: "12px" }}
          data-testid="rs-no-signals"
        >
          <span className="rs-mono-label">
            {t("retail_sentiment.insights.no_signals_title")}
          </span>
          <p
            className="m-0 mt-1.5"
            style={{
              fontSize: "13px",
              color: "var(--color-text-secondary)",
              lineHeight: 1.55,
            }}
          >
            {t("retail_sentiment.insights.no_signals_hint")}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {visibleSpikes.map((sp) => (
            <SignalAlert
              key={`${sp.ticker}-${sp.detected_at}`}
              spike={sp}
              onPick={onPickTicker}
            />
          ))}
        </div>
      )}

      {snap ? (
        <>
          <SectionLabel
            title={t("retail_sentiment.insights.lia_take")}
            meta={selected ?? ""}
          />
          <NarrativeCard snap={snap} t={t} />
        </>
      ) : null}

      <SectionLabel
        title={t("retail_sentiment.insights.framework_title")}
        meta={t("retail_sentiment.insights.framework_meta")}
      />
      <div className="grid gap-7">
        {(Object.keys(grouped) as FrameworkQuestion[]).map((q) => (
          <FrameworkSection
            key={q}
            question={q}
            metrics={grouped[q]}
            snap={snap}
            t={t}
          />
        ))}
      </div>

      <SectionLabel
        title={t("retail_sentiment.insights.reliability_title")}
        meta={t("retail_sentiment.insights.reliability_meta")}
      />
      <article
        className="rs-col-card p-5"
        style={{ borderRadius: "12px" }}
        data-testid="reliability-matrix"
      >
        <ReliabilityScatter metrics={reliabilityRows} />
      </article>
    </div>
  );
}
