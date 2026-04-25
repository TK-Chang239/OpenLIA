import { useMemo, useState } from "react";

import type { RsSnapshot } from "../../api/retail-sentiment";
import { RS_METRIC_CATALOG } from "../../lib/retail-sentiment/metric-catalog";

interface Props {
  selected: string | null;
  history: RsSnapshot[];
}

interface ContributionRow {
  metricId: string;
  label: string;
  value: number | null;
}

function decompose(snap: RsSnapshot): ContributionRow[] {
  return [
    {
      metricId: "sentiment_score",
      label: "Sentiment Score",
      value: snap.sentiment_score,
    },
    {
      metricId: "buzz_volume",
      label: "Buzz Volume (×30d)",
      value: snap.buzz_volume,
    },
    {
      metricId: "sentiment_momentum",
      label: "Momentum",
      value: snap.sentiment_momentum,
    },
    {
      metricId: "buzz_sentiment_divergence",
      label: "Divergence",
      value: snap.buzz_sentiment_divergence,
    },
    {
      metricId: "cross_source_agreement",
      label: "X-Source",
      value: snap.cross_source_agreement,
    },
    {
      metricId: "narrative_concentration",
      label: "Narrative Concentration",
      value: snap.narrative_concentration,
    },
  ];
}

export function EvidenceTab({ selected, history }: Props) {
  const [filter, setFilter] = useState<string>("all");
  const latest = history.at(-1) ?? null;

  const filtered = useMemo(() => {
    return RS_METRIC_CATALOG.filter(
      (m) => filter === "all" || m.id === filter,
    );
  }, [filter]);

  if (!selected) {
    return (
      <div className="text-sm text-[--color-text-secondary]">
        Select a single ticker to inspect its evidence feed.
      </div>
    );
  }

  if (!latest) {
    return (
      <div
        data-testid="evidence-empty"
        className="rounded-md border border-dashed border-[--color-border-subtle] p-6 text-sm text-[--color-text-secondary]"
      >
        No history for {selected} yet.
      </div>
    );
  }

  const decomposition = decompose(latest);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs uppercase text-[--color-text-secondary]">
          Filter
        </span>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          data-testid="evidence-filter"
          className="rounded-md border border-[--color-border-secondary] bg-[--color-bg-input] px-2 py-1 text-xs"
        >
          <option value="all">All metrics</option>
          {filtered.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </div>

      <section
        aria-label="Score impact decomposition"
        data-testid="evidence-decomposition"
        className="rounded-md border border-[--color-border-subtle] p-3"
      >
        <h3 className="text-xs uppercase text-[--color-text-secondary]">
          Score impact decomposition
        </h3>
        <ul className="mt-2 space-y-1">
          {decomposition.map((row) => (
            <li
              key={row.metricId}
              className="flex items-center justify-between text-sm"
            >
              <span>{row.label}</span>
              <span className="font-mono">
                {row.value === null ? "—" : row.value.toFixed(2)}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section
        aria-label="Evidence feed"
        data-testid="evidence-feed"
        className="rounded-md border border-[--color-border-subtle] p-3"
      >
        <h3 className="text-xs uppercase text-[--color-text-secondary]">
          Evidence feed (reverse chronological)
        </h3>
        <ol className="mt-2 space-y-2">
          {[...history].reverse().map((h) => (
            <li
              key={h.captured_at}
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] p-2 text-xs"
            >
              <div className="flex justify-between">
                <span>{new Date(h.captured_at).toLocaleString()}</span>
                <span>buzz×{h.buzz_volume.toFixed(2)}</span>
              </div>
              <div className="text-[--color-text-secondary]">
                sentiment={h.sentiment_score.toFixed(2)} · velocity=
                {h.social_velocity.toFixed(2)}/hr
              </div>
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
