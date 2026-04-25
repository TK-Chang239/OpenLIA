import type { RsSnapshot, RsSpike } from "../../api/retail-sentiment";
import { RS_METRIC_CATALOG } from "../../lib/retail-sentiment/metric-catalog";
import { ReliabilityBadge } from "./ReliabilityBadge";
import { SignalAlert } from "./SignalAlert";

interface Props {
  selected: string | null;
  snapshots: RsSnapshot[];
  spikes: RsSpike[];
}

function findSnapshot(
  snapshots: RsSnapshot[],
  ticker: string,
): RsSnapshot | undefined {
  return snapshots.find((s) => s.ticker === ticker);
}

function NarrativeCard({ snap }: { snap: RsSnapshot }) {
  return (
    <section
      aria-label="Narrative synthesis"
      className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4"
    >
      <h3 className="text-xs uppercase text-[--color-text-secondary]">
        Narrative synthesis
      </h3>
      <p
        data-testid="narrative-paragraph"
        className="mt-2 text-sm text-[--color-text-primary]"
      >
        {snap.narrative ?? "No narrative available — Quick-tier model not configured for this user."}
      </p>
    </section>
  );
}

function ReliabilityMatrix({ snap }: { snap: RsSnapshot }) {
  return (
    <section
      aria-label="Reliability matrix"
      data-testid="reliability-matrix"
      className="rounded-md border border-[--color-border-subtle] p-3"
    >
      <h3 className="text-xs uppercase text-[--color-text-secondary]">
        Reliability matrix
      </h3>
      <ul className="mt-2 grid grid-cols-1 gap-1 md:grid-cols-2">
        {RS_METRIC_CATALOG.map((m) => {
          const value = (snap as unknown as Record<string, number | null>)[m.id];
          return (
            <li
              key={m.id}
              className="flex items-center justify-between text-xs"
            >
              <span>{m.label}</span>
              <span className="flex items-center gap-2">
                <span className="font-mono">
                  {value === null || value === undefined
                    ? "—"
                    : Number(value).toFixed(2)}
                </span>
                <ReliabilityBadge tier={m.reliability} />
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function InsightsTab({ selected, snapshots, spikes }: Props) {
  const snap = selected ? findSnapshot(snapshots, selected) : null;
  const visibleSpikes = selected
    ? spikes.filter((sp) => sp.ticker === selected)
    : spikes;

  return (
    <div className="space-y-4">
      <section aria-label="Active signals" className="space-y-2">
        <h3 className="text-xs uppercase text-[--color-text-secondary]">
          Active signals
        </h3>
        {visibleSpikes.length === 0 ? (
          <div className="text-sm text-[--color-text-secondary]">
            No active signals.
          </div>
        ) : (
          visibleSpikes.map((sp) => (
            <SignalAlert key={`${sp.ticker}-${sp.detected_at}`} spike={sp} />
          ))
        )}
      </section>

      {snap ? (
        <>
          <NarrativeCard snap={snap} />
          <ReliabilityMatrix snap={snap} />
        </>
      ) : null}
    </div>
  );
}
