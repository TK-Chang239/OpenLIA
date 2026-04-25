export interface ReportCover {
  title: string;
  subtitle: string;
  tagline: string;
  ticker?: string | null;
  key_metrics?: { label: string; value: string; delta?: string; delta_direction?: 'up' | 'down' | 'flat' }[];
  stats_panel?: { label: string; value: string }[];
}

export interface ReportSection {
  id: string;
  title: string;
  blocks: unknown[];
}

export interface PageFurniture {
  header: { left: string; right: string };
  footer: { left: string; center: string; right: string };
  disclaimer: string;
}

export interface ReportSchema {
  schema_version: '1.0';
  department: string;
  generated_at?: string;
  page_furniture?: PageFurniture | null;
  cover: ReportCover;
  sections: ReportSection[];
}

export async function fetchReport(reportId: string): Promise<ReportSchema> {
  const res = await fetch(`/api/reports/${reportId}`, { credentials: 'include' });
  if (!res.ok) {
    throw new Error(`fetchReport failed (${res.status} ${res.statusText ?? ''})`);
  }
  const body = (await res.json()) as { schema: ReportSchema };
  return body.schema;
}

export function reportPdfUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/pdf`;
}

export function reportDocxUrl(reportId: string): string {
  return `/api/reports/${reportId}/docx`;
}
