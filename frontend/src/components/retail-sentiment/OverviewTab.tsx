import type { RsSnapshot } from "../../api/retail-sentiment";
import { RS_METRIC_BY_ID } from "../../lib/retail-sentiment/metric-catalog";
import { MetricCard } from "./MetricCard";
import { SentimentGauge } from "./SentimentGauge";

interface Props {
  selected: string | null;
  snapshots: RsSnapshot[];
}

function findSnapshot(
  snapshots: RsSnapshot[],
  ticker: string,
): RsSnapshot | undefined {
  return snapshots.find((s) => s.ticker === ticker);
}

function HeadlineTier({ snap }: { snap: RsSnapshot }) {
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
      <div className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-4">
        <div className="text-[11px] uppercase text-[--color-text-secondary]">
          Sentiment
        </div>
        <SentimentGauge score={snap.sentiment_score} />
      </div>
      <MetricCard
        label="Momentum"
        value={snap.sentiment_momentum}
        units={RS_METRIC_BY_ID.sentiment_momentum.units}
        reliability={RS_METRIC_BY_ID.sentiment_momentum.reliability}
        emphasis
      />
      <MetricCard
        label="Buzz / Sentiment Divergence"
        value={snap.buzz_sentiment_divergence}
        units={RS_METRIC_BY_ID.buzz_sentiment_divergence.units}
        reliability={RS_METRIC_BY_ID.buzz_sentiment_divergence.reliability}
        emphasis
      />
      <MetricCard
        label="Cross-Source Agreement"
        value={snap.cross_source_agreement}
        units={RS_METRIC_BY_ID.cross_source_agreement.units}
        reliability={RS_METRIC_BY_ID.cross_source_agreement.reliability}
        emphasis
      />
    </div>
  );
}

function CompactTier({ snap }: { snap: RsSnapshot }) {
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      <MetricCard
        label="Buzz Volume (×30d)"
        value={snap.buzz_volume}
        units="×"
        reliability={RS_METRIC_BY_ID.buzz_volume.reliability}
      />
      <MetricCard
        label="Buzz Count"
        value={snap.buzz_count}
        digits={0}
        reliability={RS_METRIC_BY_ID.buzz_volume.reliability}
      />
      <MetricCard
        label="Bull / Bear"
        value={snap.bull_bear_ratio}
        reliability={RS_METRIC_BY_ID.bull_bear_ratio.reliability}
      />
      <MetricCard
        label="Velocity"
        value={snap.social_velocity}
        units="/hr"
        reliability={RS_METRIC_BY_ID.social_velocity.reliability}
      />
      <MetricCard
        label="Put / Call (sentiment-adj)"
        value={snap.put_call_ratio}
        reliability={RS_METRIC_BY_ID.put_call_ratio.reliability}
      />
      <MetricCard
        label="Short Pressure"
        value={snap.short_interest_pressure}
        reliability={RS_METRIC_BY_ID.short_interest_pressure.reliability}
      />
      <MetricCard
        label="Inst./Retail Gap"
        value={snap.institutional_retail_gap}
        reliability={RS_METRIC_BY_ID.institutional_retail_gap.reliability}
      />
      <MetricCard
        label="Event Sensitivity"
        value={snap.event_sensitivity}
        reliability={RS_METRIC_BY_ID.event_sensitivity.reliability}
      />
    </div>
  );
}

function HeatMap({ snapshots }: { snapshots: RsSnapshot[] }) {
  if (snapshots.length === 0) {
    return (
      <div className="text-sm text-[--color-text-secondary]">
        No tickers tracked yet.
      </div>
    );
  }
  const cols = ["Sentiment", "Buzz×", "Momentum", "Divergence", "X-Source"];
  return (
    <div className="overflow-x-auto" data-testid="rs-heatmap">
      <table className="w-full border-separate border-spacing-1 text-xs">
        <thead>
          <tr>
            <th className="text-left">Ticker</th>
            {cols.map((c) => (
              <th key={c} className="text-left">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {snapshots.map((s) => (
            <tr key={s.ticker}>
              <td className="font-semibold">{s.ticker}</td>
              <td>{s.sentiment_score.toFixed(2)}</td>
              <td>{s.buzz_volume.toFixed(2)}</td>
              <td>{s.sentiment_momentum.toFixed(2)}</td>
              <td>{s.buzz_sentiment_divergence.toFixed(2)}</td>
              <td>{s.cross_source_agreement.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OverviewTab({ selected, snapshots }: Props) {
  if (selected === null) {
    return <HeatMap snapshots={snapshots} />;
  }
  const snap = findSnapshot(snapshots, selected);
  if (!snap) {
    return (
      <div
        data-testid="overview-empty"
        className="rounded-md border border-dashed border-[--color-border-subtle] p-6 text-sm text-[--color-text-secondary]"
      >
        No snapshot for {selected} yet — run a snapshot from the toolbar above.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <HeadlineTier snap={snap} />
      <CompactTier snap={snap} />
    </div>
  );
}
