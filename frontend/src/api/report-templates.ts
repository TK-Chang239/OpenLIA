import { ApiError, fetchJson } from "./client";

const BASE = "/api/report-templates";

export interface ReportTemplate {
  id: string;
  name: string;
  template_spec: Record<string, unknown>;
  source_markdown: string | null;
  created_at: string;
  updated_at: string;
}

interface ListResponse {
  items: ReportTemplate[];
}

export interface ParsedSection {
  id: string;
  title: string;
  brief: string;
  frontmatter: Record<string, unknown>;
}

export interface ParsedTemplate {
  global_preface: string;
  document_frontmatter: Record<string, unknown>;
  sections: ParsedSection[];
  template_spec: Record<string, unknown>;
}

export interface IngestResult {
  markdown: string;
}

export async function listReportTemplates(): Promise<ReportTemplate[]> {
  const r = await fetchJson<ListResponse>(BASE);
  return r.items;
}

export async function createReportTemplate(input: {
  name: string;
  templateSpec: Record<string, unknown>;
  sourceMarkdown?: string | null;
}): Promise<ReportTemplate> {
  return fetchJson<ReportTemplate>(BASE, {
    method: "POST",
    json: {
      name: input.name,
      template_spec: input.templateSpec,
      source_markdown: input.sourceMarkdown ?? null,
    },
  });
}

export async function updateReportTemplate(
  id: string,
  input: {
    name: string;
    templateSpec: Record<string, unknown>;
    sourceMarkdown?: string | null;
  },
): Promise<ReportTemplate> {
  return fetchJson<ReportTemplate>(`${BASE}/${id}`, {
    method: "PUT",
    json: {
      name: input.name,
      template_spec: input.templateSpec,
      source_markdown: input.sourceMarkdown ?? null,
    },
  });
}

export async function deleteReportTemplate(id: string): Promise<void> {
  await fetchJson(`${BASE}/${id}`, { method: "DELETE" });
}

export async function ingestTemplateDocument(file: File): Promise<IngestResult> {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const res = await fetch(`${BASE}/ingest`, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.json())?.detail ?? "";
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, detail || `ingest failed: ${res.status}`);
  }
  return (await res.json()) as IngestResult;
}

export async function parseTemplateMarkdown(
  markdown: string,
  name = "Untitled template",
): Promise<ParsedTemplate> {
  return fetchJson<ParsedTemplate>(`${BASE}/parse`, {
    method: "POST",
    json: { markdown, name },
  });
}
