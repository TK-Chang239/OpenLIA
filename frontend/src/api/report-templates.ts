import { ApiError, fetchJson } from "./client";

const BASE = "/api/report-templates";

export interface TemplateLoadNotice {
  kind: "reserved_key" | "unknown_key";
  key: string;
  message: string;
}

export async function fetchConversionPrompt(): Promise<string> {
  const r = await fetch(`${BASE}/conversion_prompt`);
  if (!r.ok) throw new Error(`failed: ${r.status}`);
  const { prompt } = await r.json();
  return prompt;
}

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

// ---------------------------------------------------------------------------
// v2.3 typed surface (Phase 1.5)
//
// The v2.3 parse endpoint returns a strongly-typed TemplateSpec dict that
// matches the engine's `openlia.llm.runtime.report_v2_3.templates.TemplateSpec`
// pydantic model. Validation errors come back inline as a list of strings so
// the upload modal can render them next to the parsed structure rather than
// as an HTTP error.
// ---------------------------------------------------------------------------

export interface SectionSpec {
  id: string;
  title: string;
  intent: string;
  methodology_hints: string[];
}

export interface TemplateSpec {
  template_id: string;
  name: string;
  shape_description: string;
  ticker_anchored: boolean;
  default_length?: "concise" | "normal" | "elaborative" | null;
  sections: SectionSpec[];
}

export interface ReportTemplateSummary {
  id: string;
  name: string;
  template_spec: TemplateSpec;
  source_markdown: string | null;
  created_at: string;
  updated_at: string;
}

export interface V23ParseResponse {
  template_spec: TemplateSpec | Record<string, never>;
  validation_errors: string[];
}

export async function getReportTemplate(
  id: string,
): Promise<ReportTemplateSummary> {
  return fetchJson<ReportTemplateSummary>(`${BASE}/${id}`);
}

export async function parseMarkdownV23(
  markdown: string,
  name: string,
): Promise<V23ParseResponse> {
  return fetchJson<V23ParseResponse>(`${BASE}/v23/parse`, {
    method: "POST",
    json: { markdown, name },
  });
}

export async function saveReportTemplate(input: {
  name: string;
  template_spec: TemplateSpec;
  source_markdown: string | null;
}): Promise<ReportTemplateSummary> {
  return fetchJson<ReportTemplateSummary>(BASE, {
    method: "POST",
    json: input,
  });
}

export async function ingestTemplateFile(
  file: File,
): Promise<{ markdown: string }> {
  return ingestTemplateDocument(file);
}
