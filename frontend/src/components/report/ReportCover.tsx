import type { ReportCover as ReportCoverData } from '../../api/reports';

export interface ReportCoverProps {
  cover: ReportCoverData;
}

export function ReportCover({ cover }: ReportCoverProps) {
  return (
    <header className="report-cover">
      <h1 className="report-cover__title">{cover.title}</h1>
      <div className="report-cover__subtitle">{cover.subtitle}</div>
      <p className="report-cover__tagline"><em>{cover.tagline}</em></p>
      {cover.key_metrics && cover.key_metrics.length > 0 ? (
        <div className="report-cover__metrics">
          {cover.key_metrics.map((m) => (
            <div key={m.label} className="metric-card">
              <div className="metric-card__label">{m.label}</div>
              <div className="metric-card__value">{m.value}</div>
              {m.delta ? (
                <div
                  className={`metric-card__delta metric-card__delta--${
                    m.delta_direction === 'down'
                      ? 'negative'
                      : m.delta_direction === 'flat'
                        ? 'neutral'
                        : 'positive'
                  }`}
                >
                  {m.delta}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {cover.stats_panel && cover.stats_panel.length > 0 ? (
        <dl className="report-cover__stats">
          {cover.stats_panel.map((s) => (
            <div key={s.label} className="report-cover__stat">
              <dt>{s.label}</dt>
              <dd>{s.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </header>
  );
}
