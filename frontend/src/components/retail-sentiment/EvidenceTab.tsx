import { useMemo, useState } from "react";

import type { RsSnapshot } from "../../api/retail-sentiment";
import { RS_METRIC_CATALOG } from "../../lib/retail-sentiment/metric-catalog";

interface Props {
  selected: string | null;
  history: RsSnapshot[];
}

type SourceFilter = "all" | "news" | "social";
type SourceKind = "news" | "social";

const SOURCE_LABEL: Record<string, string> = {
  eodhd_news: "EODHD news",
  fmp_yahoo: "Yahoo Finance",
  x_social: "X / Twitter",
  fmp_stocktwits: "StockTwits",
  fmp_reddit: "Reddit",
  fmp_twitter: "FMP Twitter",
};

const SOURCE_KIND: Record<string, SourceKind> = {
  eodhd_news: "news",
  fmp_yahoo: "news",
  x_social: "social",
  fmp_stocktwits: "social",
  fmp_reddit: "social",
  fmp_twitter: "social",
};

interface ImpactRow {
  id: string;
  label: string;
  value: number;
  display: string;
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

function classify(snap: RsSnapshot): "Bullish" | "Bearish" | "Mixed" {
  if (snap.sentiment_score > 0.15) return "Bullish";
  if (snap.sentiment_score < -0.15) return "Bearish";
  return "Mixed";
}

function classificationColor(label: "Bullish" | "Bearish" | "Mixed"): string {
  if (label === "Bullish") return "var(--color-feedback-success)";
  if (label === "Bearish") return "var(--color-feedback-error)";
  return "var(--color-text-secondary)";
}

function SourceFilterPills({
  active,
  onChange,
  counts,
}: {
  active: SourceFilter;
  onChange: (next: SourceFilter) => void;
  counts: Record<SourceFilter, number>;
}) {
  const items: Array<{ id: SourceFilter; label: string }> = [
    { id: "all", label: "All sources" },
    { id: "news", label: "News" },
    { id: "social", label: "Social" },
  ];
  return (
    <div
      className="flex flex-wrap items-center gap-1.5"
      data-testid="evidence-filter-row"
    >
      {items.map((it) => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            type="button"
            onClick={() => onChange(it.id)}
            data-testid={`evidence-filter-${it.id}`}
            className="inline-flex items-center gap-1.5 h-8 px-3 rounded-md border text-[12.5px] transition-colors duration-[--duration-normal]"
            style={{
              borderColor: isActive
                ? "var(--color-border-strong)"
                : "var(--color-border-subtle)",
              background: isActive
                ? "var(--color-surface-hover)"
                : "transparent",
              color: isActive
                ? "var(--color-text-primary)"
                : "var(--color-text-secondary)",
              fontWeight: isActive ? 500 : undefined,
            }}
          >
            {it.label}
            <span
              className="rs-mono-label"
              style={{ color: "var(--color-text-tertiary)" }}
            >
              {counts[it.id]}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function ScoreImpactWalkthrough({
  rows,
  baseline,
  final,
}: {
  rows: ImpactRow[];
  baseline: number;
  final: number;
}) {
  const all = [
    { id: "__baseline", label: "Baseline", value: baseline, display: baseline.toFixed(2), kind: "baseline" as const },
    ...rows.map((r) => ({ ...r, kind: "delta" as const })),
    { id: "__final", label: "= Final composite", value: final, display: final.toFixed(2), kind: "final" as const },
  ];
  const max = Math.max(
    ...all.map((r) => Math.abs(r.value)),
    0.5,
  );

  const fillFor = (kind: "baseline" | "delta" | "final", value: number) => {
    if (kind === "baseline") return "var(--color-text-tertiary)";
    if (kind === "final") return "var(--color-accent-primary)";
    if (value >= 0) return "var(--color-feedback-success)";
    return "var(--color-feedback-error)";
  };

  return (
    <ul
      className="space-y-2"
      data-testid="evidence-walkthrough"
    >
      {all.map((r) => {
        const pct = (Math.abs(r.value) / max) * 50;
        const left = r.value >= 0 ? 50 : 50 - pct;
        const width = pct;
        return (
          <li
            key={r.id}
            className="grid items-center gap-3"
            style={{ gridTemplateColumns: "180px 1fr 80px" }}
          >
            <span
              className="rs-mono-label truncate"
              style={{
                color:
                  r.kind === "final"
                    ? "var(--color-text-primary)"
                    : "var(--color-text-secondary)",
                fontWeight: r.kind === "final" ? 500 : undefined,
              }}
            >
              {r.label}
            </span>
            <span
              className="relative h-2 rounded-full"
              style={{ background: "var(--color-bg-code)" }}
              aria-hidden="true"
            >
              <span
                className="absolute inset-y-0"
                style={{
                  left: "50%",
                  width: 1,
                  background: "var(--color-border-secondary)",
                }}
              />
              <span
                className="absolute inset-y-0 rounded-full"
                style={{
                  left: `${left}%`,
                  width: `${Math.max(0.5, width)}%`,
                  background: fillFor(r.kind, r.value),
                  opacity: r.kind === "delta" ? 0.85 : 1,
                }}
              />
            </span>
            <span
              className="rs-mono-value text-[12px] text-right"
              style={{
                color:
                  r.kind === "final"
                    ? "var(--color-accent-primary)"
                    : "var(--color-text-secondary)",
              }}
            >
              {r.kind === "delta" && r.value >= 0
                ? `+${r.display}`
                : r.display}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

function SourceCard({
  source,
  count,
  snap,
  ticker,
}: {
  source: string;
  count: number;
  snap: RsSnapshot;
  ticker: string;
}) {
  const label = SOURCE_LABEL[source] ?? source;
  const kind = SOURCE_KIND[source] ?? "news";
  const stance = classify(snap);
  const color = classificationColor(stance);
  return (
    <article
      className="rs-col-card p-5 space-y-3"
      style={{ borderRadius: 12 }}
      data-testid={`evidence-source-${source}`}
    >
      <header className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <span className="rs-mono-label">
            {kind === "news" ? "News provider" : "Social provider"}
          </span>
          <h4
            className="m-0"
            style={{
              fontSize: 14,
              fontWeight: 500,
              color: "var(--color-text-primary)",
            }}
          >
            {label}
          </h4>
        </div>
        <span
          className="rs-mono-label px-2 py-1 rounded shrink-0"
          style={{
            background: "var(--color-bg-code)",
            color,
            fontSize: 10,
            letterSpacing: "0.14em",
          }}
        >
          {stance}
        </span>
      </header>
      <p
        className="m-0"
        style={{
          fontSize: 13,
          lineHeight: 1.55,
          color: "var(--color-text-secondary)",
        }}
      >
        Captured {count.toLocaleString()} mentions of{" "}
        <strong style={{ color: "var(--color-text-primary)" }}>{ticker}</strong>{" "}
        on this source. Per-source polarity is not yet broken out — the stance
        badge above reflects the snapshot-wide composite.
      </p>
      <dl
        className="font-mono"
        style={{
          fontSize: 11.5,
          color: "var(--color-text-secondary)",
        }}
      >
        <div className="flex items-center gap-2">
          <dt
            className="rs-mono-label"
            style={{ minWidth: 96 }}
          >
            count
          </dt>
          <dd className="m-0" style={{ color: "var(--color-text-primary)" }}>
            {count}
          </dd>
        </div>
        <div className="flex items-center gap-2">
          <dt
            className="rs-mono-label"
            style={{ minWidth: 96 }}
          >
            normalized
          </dt>
          <dd className="m-0" style={{ color: "var(--color-text-primary)" }}>
            {snap.sentiment_score.toFixed(2)} <span style={{ color: "var(--color-text-tertiary)" }}>(snapshot-wide)</span>
          </dd>
        </div>
      </dl>
    </article>
  );
}

function ChatStyleSnapshotRow({
  snap,
  prior,
}: {
  snap: RsSnapshot;
  prior: RsSnapshot | null;
}) {
  const delta =
    prior && Number.isFinite(snap.sentiment_score) && Number.isFinite(prior.sentiment_score)
      ? snap.sentiment_score - prior.sentiment_score
      : null;
  const stance = classify(snap);
  const stanceColor = classificationColor(stance);
  const captured = new Date(snap.captured_at);
  const sources = Object.keys(snap.source_breakdown ?? {});

  return (
    <div
      className="grid gap-3.5 px-5 py-4"
      style={{
        gridTemplateColumns: "84px 1fr",
        borderBottom: "1px solid var(--color-border-subtle)",
      }}
    >
      <div className="rs-mono-label leading-tight">
        <span className="block text-[--color-text-primary] font-medium">
          {captured.toLocaleDateString(undefined, {
            month: "short",
            day: "2-digit",
          })}
        </span>
        <span className="block mt-0.5">
          {captured.toLocaleTimeString(undefined, {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <div className="min-w-0 flex flex-col gap-1.5">
        <p
          className="m-0"
          style={{
            fontSize: "13.5px",
            lineHeight: 1.55,
            color: "var(--color-text-primary)",
          }}
        >
          {snap.narrative ?? (
            <span className="text-[--color-text-tertiary]">
              No narrative for this snapshot. Score reflects aggregated
              classifier output.
            </span>
          )}
        </p>
        <div className="flex flex-wrap items-center gap-2.5 rs-mono-label">
          <span
            className="px-1.5 py-0.5 rounded"
            style={{
              background: "var(--color-bg-code)",
              color: "var(--color-text-primary)",
            }}
          >
            {snap.ticker}
          </span>
          <span
            className="px-1.5 py-0.5 rounded"
            style={{
              background: "var(--color-bg-code)",
              color: stanceColor,
            }}
          >
            {stance.toUpperCase()}
          </span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            score {snap.sentiment_score.toFixed(2)}
          </span>
          <span style={{ color: "var(--color-text-tertiary)" }}>
            buzz × {(snap.buzz_volume ?? 0).toFixed(2)}
          </span>
          {delta !== null ? (
            <span
              style={{
                color:
                  delta >= 0
                    ? "var(--color-feedback-success)"
                    : "var(--color-feedback-error)",
              }}
            >
              Δ {delta >= 0 ? "+" : ""}
              {delta.toFixed(2)}
            </span>
          ) : null}
          <span style={{ color: "var(--color-text-tertiary)" }}>
            sources · {sources.length}
          </span>
        </div>
      </div>
    </div>
  );
}

function impactRowsFor(snap: RsSnapshot): ImpactRow[] {
  const rows: Array<[string, number | null, string | null]> = [
    ["sentiment_score", snap.sentiment_score, null],
    ["sentiment_momentum", snap.sentiment_momentum, null],
    [
      "bull_bear_ratio",
      Number.isFinite(snap.bull_bear_ratio) ? snap.bull_bear_ratio - 0.5 : null,
      "bull/bear (centered)",
    ],
    [
      "buzz_volume",
      Number.isFinite(snap.buzz_volume) ? snap.buzz_volume - 1.0 : null,
      "buzz × (vs 30d)",
    ],
    [
      "buzz_sentiment_divergence",
      Number.isFinite(snap.buzz_sentiment_divergence)
        ? -snap.buzz_sentiment_divergence
        : null,
      "divergence (sign flipped)",
    ],
    [
      "cross_source_agreement",
      Number.isFinite(snap.cross_source_agreement)
        ? snap.cross_source_agreement - 0.5
        : null,
      "x-source (centered)",
    ],
  ];
  const out: ImpactRow[] = [];
  for (const [id, value, override] of rows) {
    if (value === null || !Number.isFinite(value)) continue;
    const meta = RS_METRIC_CATALOG.find((m) => m.id === id);
    out.push({
      id,
      label: override ?? meta?.label ?? id,
      value,
      display: value.toFixed(2),
    });
  }
  return out;
}

export function EvidenceTab({ selected, history }: Props) {
  const [filter, setFilter] = useState<SourceFilter>("all");

  if (!selected) {
    return (
      <div
        className="rs-col-card p-8 text-center"
        style={{ borderRadius: 12 }}
      >
        <p
          className="m-0"
          style={{
            fontSize: 14,
            lineHeight: 1.55,
            color: "var(--color-text-secondary)",
          }}
        >
          Select a single ticker to inspect the evidence behind its score.
        </p>
      </div>
    );
  }

  const sorted = useMemo(
    () =>
      [...history].sort((a, b) => a.captured_at.localeCompare(b.captured_at)),
    [history],
  );
  const latest = sorted.at(-1) ?? null;

  if (!latest) {
    return (
      <div
        data-testid="evidence-empty"
        className="rs-col-card p-8 text-center"
        style={{ borderRadius: 12 }}
      >
        <p className="rs-mono-label">No history</p>
        <p
          className="m-0 mt-2"
          style={{ color: "var(--color-text-secondary)" }}
        >
          No snapshot history for {selected} yet — run a snapshot to populate
          this view.
        </p>
      </div>
    );
  }

  const breakdown = latest.source_breakdown ?? {};
  const sourceEntries = Object.entries(breakdown).filter(
    ([, v]) => typeof v === "number" && v > 0,
  ) as Array<[string, number]>;

  const counts: Record<SourceFilter, number> = {
    all: sourceEntries.length,
    news: sourceEntries.filter(([k]) => SOURCE_KIND[k] === "news").length,
    social: sourceEntries.filter(([k]) => SOURCE_KIND[k] === "social").length,
  };
  const filtered = sourceEntries.filter(([k]) =>
    filter === "all" ? true : SOURCE_KIND[k] === filter,
  );

  const impactRows = impactRowsFor(latest);
  const finalScore = impactRows.reduce((acc, r) => acc + r.value, 0);

  return (
    <div className="space-y-7" data-testid="evidence-tab">
      <header className="space-y-2">
        <h2
          className="m-0"
          style={{
            fontSize: 22,
            fontWeight: 500,
            color: "var(--color-text-primary)",
            letterSpacing: "-0.01em",
          }}
        >
          Evidence snapshots
        </h2>
        <p
          className="m-0 max-w-[760px]"
          style={{
            fontSize: 13.5,
            lineHeight: 1.6,
            color: "var(--color-text-secondary)",
          }}
        >
          Every score on the dashboard is built from concrete sources. Here is
          how today's mentions are distributed and how the composite read is
          assembled metric by metric.
        </p>
      </header>

      <SectionLabel
        title="Sources"
        meta={`${sourceEntries.length} active · filter ${filter}`}
        first
      />
      <SourceFilterPills
        active={filter}
        onChange={setFilter}
        counts={counts}
      />

      {filtered.length === 0 ? (
        <div
          className="rs-col-card p-6 text-center"
          style={{ borderRadius: 12 }}
          data-testid="evidence-no-sources"
        >
          <p className="rs-mono-label">No matching sources</p>
          <p
            className="m-0 mt-2"
            style={{ color: "var(--color-text-secondary)", fontSize: 13 }}
          >
            {sourceEntries.length === 0
              ? "Snapshot did not record any source breakdown — provider may be misconfigured."
              : "No sources of this kind in the latest snapshot. Try the All filter."}
          </p>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map(([k, count]) => (
            <SourceCard
              key={k}
              source={k}
              count={count}
              snap={latest}
              ticker={selected}
            />
          ))}
        </div>
      )}
      <p
        className="rs-mono-label"
        style={{ color: "var(--color-text-tertiary)" }}
      >
        Backend gap: per-source polarity / engagement / per-evidence-item rows
        require an /evidence_items endpoint (Gap 2 + Gap 3).
      </p>

      <SectionLabel
        title="Score impact walkthrough"
        meta={`Snapshot · ${new Date(latest.captured_at).toLocaleString()}`}
      />
      <article
        className="rs-col-card p-5"
        data-testid="evidence-decomposition"
        style={{ borderRadius: 12 }}
      >
        <ScoreImpactWalkthrough
          rows={impactRows}
          baseline={0}
          final={finalScore}
        />
        <p
          className="rs-mono-label mt-4"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          Backend gap: real per-evidence walkthrough (+ Reuters article, − NHTSA
          probe, etc.) requires per-item additive impact (Gap 4). Today's bars
          are signed contributions of each composite metric, centered against
          its neutral value.
        </p>
      </article>

      <SectionLabel
        title="Recent snapshots"
        meta={`${sorted.length} captures · reverse chronological`}
      />
      <article
        className="rs-col-card overflow-hidden"
        data-testid="evidence-feed"
        style={{ borderRadius: 12 }}
      >
        {[...sorted].reverse().map((snap, i, arr) => {
          const isLast = i === arr.length - 1;
          return (
            <ChatStyleSnapshotRow
              key={snap.captured_at}
              snap={snap}
              prior={isLast ? null : arr[i + 1]}
            />
          );
        })}
        <div
          className="rs-mono-label px-5 py-3"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          Backend gap: per-source rows (article / tweet / post with
          classification badge + impact value) require an /evidence_items
          endpoint. Snapshot history shown here is the closest substitute today.
        </div>
      </article>
    </div>
  );
}
