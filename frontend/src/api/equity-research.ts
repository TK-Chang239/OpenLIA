import { fetchJson } from "./client";

export type ReportMode = "stock_initiation" | "stock_update" | "sector_research";
export type ReportLength = "concise" | "normal" | "elaborative";
// 3-state UI pill on the report settings modal. "off" = thinking disabled
// (the server reads this as None / null). "medium" / "high" map to the
// per-provider thinking budget in the v2.3 wiring layer.
export type ReportReasoningEffort = "off" | "medium" | "high";
export type TemplateOwnerScope = "global" | "user";
export type TemplateSelection = "default" | string;

export interface CustomSection {
  id: string;
  title: string;
  description: string | null;
}

export interface ErConfig {
  report_mode: ReportMode;
  report_length: ReportLength;
  // User-selected extended-thinking effort, shared across all report modes.
  // Optional on the wire because the server-side ErUserConfig persistence
  // is a follow-up; until then the field round-trips as React state on the
  // active modal session. Consumers should treat ``undefined`` as ``"off"``.
  report_reasoning_effort?: ReportReasoningEffort;
  sections_by_mode: Record<ReportMode, string[]>;
  custom_sections_by_mode: Record<ReportMode, CustomSection[]>;
  selected_template_id_by_mode: Record<ReportMode, TemplateSelection>;
  // Phase 5f: per-mode web-search budget override. Absent keys mean
  // "use framework default" (resolved server-side at report-run time).
  web_search_budgets_by_mode: Partial<Record<ReportMode, number>>;
}

export interface ErConfigPatch {
  report_mode?: ReportMode;
  report_length?: ReportLength;
  report_reasoning_effort?: ReportReasoningEffort;
  sections_by_mode?: Partial<Record<ReportMode, string[]>>;
  custom_sections_by_mode?: Partial<Record<ReportMode, CustomSection[]>>;
  selected_template_id_by_mode?: Partial<Record<ReportMode, TemplateSelection>>;
  web_search_budgets_by_mode?: Partial<Record<ReportMode, number>>;
}

// Framework defaults — shown as placeholder values in the stepper UI
// when the user hasn't recorded an override for a mode. Source of
// truth is `packages/core/src/openlia/reports/frameworks/*.json`;
// duplicated here so the UI can render before the first PUT.
export const WEB_SEARCH_BUDGET_DEFAULTS: Record<ReportMode, number> = {
  stock_initiation: 10,
  stock_update: 5,
  sector_research: 15,
};

// Safe defaults used as initial config state so the page can paint its
// welcome view on the first frame without waiting for the GET round-trip.
// The real server config replaces this in place as soon as it arrives.
export const ER_CONFIG_DEFAULTS: ErConfig = {
  report_mode: "stock_initiation",
  report_length: "normal",
  report_reasoning_effort: "off",
  sections_by_mode: {
    stock_initiation: [],
    stock_update: [],
    sector_research: [],
  },
  custom_sections_by_mode: {
    stock_initiation: [],
    stock_update: [],
    sector_research: [],
  },
  selected_template_id_by_mode: {
    stock_initiation: "default",
    stock_update: "default",
    sector_research: "default",
  },
  web_search_budgets_by_mode: {},
};

export interface ErTemplate {
  id: string;
  owner_scope: TemplateOwnerScope;
  owner_user_id: string | null;
  created_by_user_id: string | null;
  name: string;
  compatible_modes: ReportMode[];
  raw_filename: string;
  raw_mime: string;
  raw_size_bytes: number;
  char_count: number;
  estimated_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface ErTemplateListResponse {
  templates: ErTemplate[];
}

export interface ErTemplateUploadInput {
  file: File;
  name?: string;
  compatibleModes: ReportMode[];
  scope: TemplateOwnerScope;
}

const CONFIG_PATH = "/api/departments/equity-research/config";
const REPORT_PATH = "/api/departments/equity-research/report";
const CHAT_PATH = "/api/departments/equity-research/chat";
const TEMPLATES_PATH = "/api/departments/equity-research/templates";

export async function fetchErConfig(): Promise<ErConfig> {
  return fetchJson<ErConfig>(CONFIG_PATH);
}

export async function updateErConfig(patch: ErConfigPatch): Promise<ErConfig> {
  return fetchJson<ErConfig>(CONFIG_PATH, {
    method: "PUT",
    json: patch,
  });
}

export async function listErTemplates(): Promise<ErTemplate[]> {
  const r = await fetchJson<ErTemplateListResponse | null>(TEMPLATES_PATH);
  if (!r || !Array.isArray(r.templates)) {
    throw new Error(
      "Templates endpoint returned no JSON. Restart the backend (and run alembic upgrade head) to pick up the new /templates routes.",
    );
  }
  return r.templates;
}

export async function uploadErTemplate(input: ErTemplateUploadInput): Promise<ErTemplate> {
  const fd = new FormData();
  fd.append("file", input.file, input.file.name);
  if (input.name) fd.append("name", input.name);
  fd.append("compatible_modes", input.compatibleModes.join(","));
  fd.append("scope", input.scope);
  const res = await fetch(TEMPLATES_PATH, {
    method: "POST",
    credentials: "include",
    body: fd,
  });
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body?.detail ?? "";
    } catch {
      detail = await res.text();
    }
    throw new Error(detail || `upload failed: ${res.status}`);
  }
  return (await res.json()) as ErTemplate;
}

export async function patchErTemplate(
  id: string,
  patch: { name?: string; compatible_modes?: ReportMode[] },
): Promise<ErTemplate> {
  return fetchJson<ErTemplate>(`${TEMPLATES_PATH}/${id}`, {
    method: "PATCH",
    json: patch,
  });
}

export async function deleteErTemplate(id: string): Promise<void> {
  await fetchJson(`${TEMPLATES_PATH}/${id}`, { method: "DELETE" });
}

export async function fetchErTemplateExtractedText(id: string): Promise<string> {
  const r = await fetchJson<{ id: string; extracted_text: string }>(
    `${TEMPLATES_PATH}/${id}/extracted_text`,
  );
  return r.extracted_text;
}

export function erTemplateRawUrl(id: string): string {
  return `${TEMPLATES_PATH}/${id}/raw`;
}

export function reportStreamUrl(): string {
  return REPORT_PATH;
}

export function chatStreamUrl(): string {
  return CHAT_PATH;
}
