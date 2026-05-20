import { useTranslation } from 'react-i18next';

import type { ReportCover as ReportCoverData } from '../../api/reports';
import { CitationRefs } from './CitationRefs';

export interface ReportCoverProps {
  cover: ReportCoverData;
}

function formatConsensusTarget(value: number): string {
  // Match the report-wide price formatter: dollars, two decimals, thousands separator.
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatUpsidePct(value: number): string {
  // consensus_upside_pct is a decimal (0.225 = 22.5%).
  const pct = value * 100;
  const sign = pct >= 0 ? '+' : '';
  return `${sign}${pct.toFixed(1)}%`;
}

function ConsensusBlock({ cover }: { cover: ReportCoverData }) {
  // WS5: render the deterministic consensus block (rating badge + mean
  // target + upside chip) immediately under the subtitle so the market
  // verdict appears above the fold rather than at the document tail.
  // All three fields populate from server-side facts; absent fields
  // degrade gracefully.
  const { t } = useTranslation();
  const rating = cover.consensus_rating;
  const target = cover.consensus_target_mean;
  const upside = cover.consensus_upside_pct;
  if (rating == null && target == null && upside == null) return null;
  const upsideTone = upside == null ? 'neutral' : upside >= 0 ? 'positive' : 'negative';
  return (
    <div className="report-cover__consensus" data-testid="report-cover-consensus">
      {rating ? (
        <span className="report-cover__consensus-badge" data-tone="neutral">
          <span className="report-cover__consensus-badge-label">
            {t('report.consensus_rating_label', 'Consensus')}
          </span>
          <span className="report-cover__consensus-badge-value">{rating}</span>
        </span>
      ) : null}
      {target != null ? (
        <span className="report-cover__consensus-target">
          <span className="report-cover__consensus-target-label">
            {t('report.consensus_mean_target_label', 'Mean target')}
          </span>
          <span className="report-cover__consensus-target-value">
            {formatConsensusTarget(target)}
          </span>
          {upside != null ? (
            <span
              className="report-cover__consensus-upside"
              data-tone={upsideTone}
            >
              {formatUpsidePct(upside)}
            </span>
          ) : null}
        </span>
      ) : null}
      <CitationRefs ids={cover.consensus_source_ids} />
    </div>
  );
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
  const { t } = useTranslation();
  const tldrLabel = cover.tldr_label ?? t('report.executive_summary');
  return (
    <header className="report-cover">
      {cover.eyebrow ? <div className="report-cover__eyebrow">{cover.eyebrow}</div> : null}
      <h1 className="report-cover__title">{cover.title}</h1>
      <div className="report-cover__subtitle">{cover.subtitle}</div>
      {/* Design judgment: place the consensus block between subtitle and
          tagline so the deterministic rating/target/upside sits above the
          fold next to the company name, but below the visual hierarchy of
          the title itself. */}
      <ConsensusBlock cover={cover} />
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
