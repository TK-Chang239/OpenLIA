import type { MetaStats } from '../../api/reports';

export interface MetaStatsCardProps {
  stats: MetaStats;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}k`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function formatReadTime(m: number): string {
  if (m <= 1) return '1 min read';
  return `${m} min read`;
}

export function MetaStatsCard({ stats }: MetaStatsCardProps) {
  const rows: { label: string; value: string }[] = [
    { label: 'Sections', value: String(stats.sections_count) },
    { label: 'Sources', value: String(stats.sources_count) },
    { label: 'Read time', value: formatReadTime(stats.est_read_minutes) },
  ];
  if (stats.web_search_queries != null && stats.web_search_queries > 0) {
    rows.push({ label: 'Web searches', value: String(stats.web_search_queries) });
  }
  if (stats.narrative_coverage_label) {
    const pct = stats.narrative_coverage_pct;
    const suffix = pct != null ? ` (${Math.round(pct * 100)}%)` : '';
    rows.push({
      label: 'Narrative coverage',
      value: `${stats.narrative_coverage_label}${suffix}`,
    });
  }
  if (stats.tokens_used != null && stats.tokens_used > 0) {
    rows.push({ label: 'Tokens', value: formatTokens(stats.tokens_used) });
  }
  if (stats.model_id) {
    rows.push({ label: 'Model', value: stats.model_id });
  }
  return (
    <section
      className="report-meta-stats"
      aria-label="Report statistic summary"
    >
      <div className="report-meta-stats__label">Report Stats</div>
      <dl className="report-meta-stats__list">
        {rows.map((r) => (
          <div key={r.label} className="report-meta-stats__row">
            <dt>{r.label}</dt>
            <dd>{r.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
