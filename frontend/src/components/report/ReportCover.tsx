import type { ReportCover as ReportCoverData } from '../../api/reports';

export interface ReportCoverProps {
  cover: ReportCoverData;
}

function MetricCell({ metric }: { metric: NonNullable<ReportCoverData['key_metrics']>[number] }) {
  const tone = metric.tag?.tone ?? metric.delta_direction;
  const deltaClass =
    metric.delta_direction === 'down'
      ? 'report-cover__metric-delta--down'
      : metric.delta_direction === 'flat'
        ? 'report-cover__metric-delta--flat'
        : metric.delta_direction === 'up'
          ? 'report-cover__metric-delta--up'
          : '';
  return (
    <div className={`report-cover__meta-cell${metric.highlight ? ' is-highlighted' : ''}`}>
      <div className="report-cover__meta-label">{metric.label}</div>
      <div className="report-cover__meta-value">{metric.value}</div>
      {metric.delta ? (
        <div className={`report-cover__meta-delta ${deltaClass}`} data-tone={tone ?? 'neutral'}>
          {metric.delta}
        </div>
      ) : null}
      {metric.tag ? (
        <span className="report-cover__meta-tag" data-tone={metric.tag.tone ?? 'neutral'}>
          {metric.tag.label}
        </span>
      ) : null}
      {metric.context ? <div className="report-cover__meta-context">{metric.context}</div> : null}
    </div>
  );
}

export function ReportCover({ cover }: ReportCoverProps) {
  const tldrLabel = cover.tldr_label ?? 'Executive Summary';
  return (
    <header className="report-cover">
      {cover.eyebrow ? <div className="report-cover__eyebrow">{cover.eyebrow}</div> : null}
      <h1 className="report-cover__title">{cover.title}</h1>
      <div className="report-cover__subtitle">{cover.subtitle}</div>
      <p className="report-cover__tagline">{cover.tagline}</p>
      {cover.key_metrics && cover.key_metrics.length > 0 ? (
        <div className="report-cover__meta-strip">
          {cover.key_metrics.map((m) => (
            <MetricCell key={m.label} metric={m} />
          ))}
        </div>
      ) : null}
      {cover.tldr && cover.tldr.length > 0 ? (
        <aside className="report-cover__tldr">
          <div className="report-cover__tldr-label">{tldrLabel}</div>
          {cover.tldr.map((p, i) => (
            <p key={i} className="report-cover__tldr-paragraph">{p}</p>
          ))}
        </aside>
      ) : null}
    </header>
  );
}
