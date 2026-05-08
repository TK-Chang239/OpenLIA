import { useMemo } from "react";

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
}: {
  m: MetricDefinition;
  value: number | null;
}) {
  let answer = "—";
  let tone = "var(--color-text-secondary)";

  if (value === null) {
    answer = "Awaiting data";
    tone = "var(--color-text-tertiary)";
  } else if (m.id === "sentiment_score") {
    answer = value >= 0.1 ? "Bullish" : value <= -0.1 ? "Bearish" : "Balanced";
    tone =
      value >= 0.1
        ? "var(--color-feedback-success)"
        : value <= -0.1
          ? "var(--color-feedback-error)"
          : "var(--color-text-secondary)";
  } else if (m.id === "buzz_volume") {
    answer = value > 1.5 ? "Spike" : value > 1.0 ? "Elevated" : "Normal";
    tone =
      value > 1.5
        ? "var(--color-feedback-error)"
        : value > 1.0
          ? "var(--color-feedback-warning)"
          : "var(--color-text-secondary)";
  } else if (m.id === "sentiment_momentum") {
    answer = value > 0.02 ? "Improving" : value < -0.02 ? "Deteriorating" : "Flat";
    tone =
      value > 0.02
        ? "var(--color-feedback-success)"
        : value < -0.02
          ? "var(--color-feedback-error)"
          : "var(--color-text-secondary)";
  } else if (m.id === "bull_bear_ratio") {
    answer =
      value > 0.7
        ? "Crowded long"
        : value < 0.3
          ? "Crowded short"
          : "Mixed";
    tone =
      value > 0.7 || value < 0.3
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  } else if (m.id === "buzz_sentiment_divergence") {
    answer = value > 1 ? "Panic" : value < -1 ? "Stealth bid" : "No edge";
    tone =
      value > 1
        ? "var(--color-feedback-error)"
        : value < -1
          ? "var(--color-feedback-success)"
          : "var(--color-text-secondary)";
  } else if (m.id === "social_velocity") {
    answer = value > 1 ? "Accelerating" : value < -0.5 ? "Decelerating" : "Steady";
    tone =
      value > 1
        ? "var(--color-feedback-warning)"
        : "var(--color-text-secondary)";
  } else if (m.id === "cross_source_agreement") {
    answer = value > 0.7 ? "High" : value > 0.4 ? "Mixed" : "Low";
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
}: {
  question: FrameworkQuestion;
  metrics: MetricDefinition[];
  snap: RsSnapshot | null;
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
          />
        ))}
      </div>
    </section>
  );
}

function NarrativeCard({ snap }: { snap: RsSnapshot }) {
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
        <span className="rs-mono-label">Narrative synthesis</span>
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
              No narrative synthesis yet — Quick-tier model not configured for
              this user.
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
        title="Active signals"
        meta={`${visibleSpikes.length} alerts`}
        first
      />
      {visibleSpikes.length === 0 ? (
        <div
          className="rs-col-card p-5"
          style={{ borderRadius: "12px" }}
          data-testid="rs-no-signals"
        >
          <span className="rs-mono-label">No active signals</span>
          <p
            className="m-0 mt-1.5"
            style={{
              fontSize: "13px",
              color: "var(--color-text-secondary)",
              lineHeight: 1.55,
            }}
          >
            Buzz spikes, divergences, and momentum crossovers will surface here
            when thresholds breach. Velocity surfaces here as a derived trigger
            (see Metrics Deep Dive for thresholds).
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
          <SectionLabel title="LIA take" meta={selected ?? ""} />
          <NarrativeCard snap={snap} />
        </>
      ) : null}

      <SectionLabel title="Insights framework" meta="six questions" />
      <div className="grid gap-7">
        {(Object.keys(grouped) as FrameworkQuestion[]).map((q) => (
          <FrameworkSection
            key={q}
            question={q}
            metrics={grouped[q]}
            snap={snap}
          />
        ))}
      </div>

      <SectionLabel
        title="Reliability matrix"
        meta="predictive strength × timeliness · bubble = data volume"
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
