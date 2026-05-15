import { CitationRefs } from '../CitationRefs';

export interface Metric {
  label: string;
  value: string;
  delta?: string;
  delta_direction?: 'up' | 'down' | 'flat';
  source_ids?: string[];
}

export interface MetricCardsBlockProps {
  type: 'metric_cards';
  metrics: Metric[];
}

function deltaClass(direction?: 'up' | 'down' | 'flat'): string {
  if (direction === 'up') return 'metric-card__delta--positive';
  if (direction === 'down') return 'metric-card__delta--negative';
  return 'metric-card__delta--neutral';
}

export function MetricCardsBlock({ metrics }: MetricCardsBlockProps) {
  return (
    <div className="metric-cards">
      {metrics.map((m) => (
        <div key={m.label} className="metric-card">
          <div className="metric-card__label">{m.label}</div>
          <div className="metric-card__value">
            {m.value}
            {!m.delta ? <CitationRefs ids={m.source_ids} /> : null}
          </div>
          {m.delta ? (
            <div className={`metric-card__delta ${deltaClass(m.delta_direction)}`}>
              {m.delta}
              <CitationRefs ids={m.source_ids} />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
