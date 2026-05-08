export type Tone = 'positive' | 'negative' | 'neutral' | 'warn';
export type DeltaDirection = 'up' | 'down' | 'flat';

export interface Tag {
  label: string;
  tone?: Tone;
}

export interface Metric {
  label: string;
  value: string;
  delta?: string | null;
  delta_direction?: DeltaDirection | null;
  context?: string | null;
  tag?: Tag | null;
  highlight?: boolean;
}

export interface ReportCover {
  title: string;
  subtitle: string;
  eyebrow?: string | null;
  ticker?: string | null;
  tagline: string;
  tldr?: string[];
  tldr_label?: string | null;
  key_metrics?: Metric[];
}

export interface ReportSection {
  id: string;
  title: string;
  blocks: ReportBlock[];
}

export interface PageFurniture {
  header: { left: string; right: string };
  footer: { left: string; center: string; right: string };
  disclaimer: string;
}

export interface Verdict {
  rating: string;
  previous_rating?: string | null;
  target?: string | null;
  upside?: string | null;
  as_of?: string | null;
}

export interface SparklinePoint {
  x: number;
  y: number;
}

export interface Sparkline {
  label: string;
  points: SparklinePoint[];
}

export interface Rail {
  verdict?: Verdict | null;
  quick_stats?: Metric[];
  sparkline?: Sparkline | null;
}

export interface Citation {
  id: string;
  title: string;
  source?: string | null;
  url?: string | null;
  date?: string | null;
}

// ─── Block discriminated union ─────────────────────────────────────────────
export type Align = 'left' | 'center' | 'right';
export type FormatRule =
  | 'negative'
  | 'positive'
  | 'directional'
  | 'bold'
  | 'muted'
  | 'tag-beat'
  | 'tag-miss'
  | 'tag-info';

export interface TextBlock { type: 'text'; content: string; }
export interface KeyFindingBlock { type: 'key_finding'; content: string; }
export interface PullQuoteBlock {
  type: 'pull_quote';
  text: string;
  attribution?: string | null;
  source?: string | null;
  timestamp?: string | null;
}
export interface RatingBadgeBlock {
  type: 'rating_badge';
  rating: string;
  previous_rating?: string | null;
  change_date?: string | null;
}
export interface MetricCardsBlock { type: 'metric_cards'; metrics: Metric[]; }
export interface TableHeaderSpec {
  key: string;
  label: string;
  align?: Align;
  sortable?: boolean;
  sparkline?: boolean;
}
export interface TableBlock {
  type: 'table';
  title: string;
  headers: TableHeaderSpec[];
  rows: Record<string, unknown>[];
  cell_format?: Record<string, { rule: FormatRule }>;
  footnotes?: string[];
  options?: Record<string, unknown>;
}

export interface CalloutItem {
  eyebrow?: string | null;
  title: string;
  description: string;
}
export interface CalloutGridBlock {
  type: 'callout_grid';
  columns?: 2 | 3 | 4;
  items: CalloutItem[];
}

export interface TimelineEvent {
  when: string;
  what: string;
  impact?: string | null;
  impact_tag?: Tag | null;
  highlight?: boolean;
}
export interface TimelineBlock {
  type: 'timeline';
  title?: string | null;
  events: TimelineEvent[];
}

export interface BulletListBlock {
  type: 'bullet_list';
  items: string[];
  tone?: 'default' | 'positive' | 'negative';
}

export interface ComparisonColumn {
  title: string;
  tone?: Tone;
  items: string[];
}
export interface ComparisonSplitBlock {
  type: 'comparison_split';
  left: ComparisonColumn;
  right: ComparisonColumn;
}

export interface QuoteBlock {
  type: 'quote';
  text: string;
  speaker?: string | null;
  role?: string | null;
  tag?: Tag | null;
  timestamp?: string | null;
}

// Charts (kept loose — existing chart renderers consume the raw shapes).
export interface ChartLikeBlock {
  type:
    | 'line_chart'
    | 'bar_chart'
    | 'area_chart'
    | 'pie_chart'
    | 'candlestick_chart'
    | 'waterfall_chart'
    | 'scatter_plot'
    | 'heatmap'
    | 'treemap'
    | 'combo_chart';
  [k: string]: unknown;
}

export interface GroupBlock {
  type: 'group';
  columns: 1 | 2 | 3 | 4;
  blocks: ReportBlock[];
}

export type ReportBlock =
  | TextBlock
  | KeyFindingBlock
  | PullQuoteBlock
  | RatingBadgeBlock
  | MetricCardsBlock
  | TableBlock
  | CalloutGridBlock
  | TimelineBlock
  | BulletListBlock
  | ComparisonSplitBlock
  | QuoteBlock
  | ChartLikeBlock
  | GroupBlock;

export interface ReportSchema {
  schema_version: '2.0';
  department: string;
  generated_at?: string;
  page_furniture?: PageFurniture | null;
  cover: ReportCover;
  sections: ReportSection[];
  rail?: Rail | null;
  citations?: Citation[];
}

export async function fetchReport(reportId: string): Promise<ReportSchema> {
  if (reportId.startsWith('demo-') && import.meta.env?.MODE !== 'test') {
    const { getDemoReportSchema } = await import('../lib/earnings-update/demo-reports');
    return getDemoReportSchema(reportId);
  }
  const res = await fetch(`/api/reports/${reportId}`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`fetchReport failed (${res.status} ${res.statusText ?? ''})`);
  }
  const body = (await res.json()) as { schema: ReportSchema };
  return body.schema;
}

export interface ReportListItem {
  id: string;
  department: string;
  report_type: string;
  title: string;
  created_at: string;
  source_session_id?: string | null;
}

export interface ReportListResponse {
  items: ReportListItem[];
}

export async function listReports(params: {
  department?: string;
  session_id?: string;
} = {}): Promise<ReportListResponse> {
  const search = new URLSearchParams();
  if (params.department) search.set('department', params.department);
  if (params.session_id) search.set('session_id', params.session_id);
  const qs = search.toString();
  const res = await fetch(`/api/reports${qs ? `?${qs}` : ''}`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`listReports failed (${res.status} ${res.statusText ?? ''})`);
  }
  return (await res.json()) as ReportListResponse;
}

export function reportPdfUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/pdf`;
}

export function reportDocxUrl(reportId: string): string {
  return `/api/reports/${reportId}/docx`;
}
