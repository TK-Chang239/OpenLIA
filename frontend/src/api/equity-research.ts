import { fetchJson } from "./client";

export type ReportMode = "stock_initiation" | "stock_update" | "sector_research";
export type ReportLength = "concise" | "normal" | "elaborative";

export interface CustomSection {
  id: string;
  title: string;
  description: string | null;
}

export interface ErConfig {
  report_mode: ReportMode;
  report_length: ReportLength;
  sections_by_mode: Record<ReportMode, string[]>;
  custom_sections_by_mode: Record<ReportMode, CustomSection[]>;
}

export interface ErConfigPatch {
  report_mode?: ReportMode;
  report_length?: ReportLength;
  sections_by_mode?: Partial<Record<ReportMode, string[]>>;
  custom_sections_by_mode?: Partial<Record<ReportMode, CustomSection[]>>;
}

const CONFIG_PATH = "/api/departments/equity-research/config";
const REPORT_PATH = "/api/departments/equity-research/report";
const CHAT_PATH = "/api/departments/equity-research/chat";

export async function fetchErConfig(): Promise<ErConfig> {
  return fetchJson<ErConfig>(CONFIG_PATH);
}

export async function updateErConfig(patch: ErConfigPatch): Promise<ErConfig> {
  return fetchJson<ErConfig>(CONFIG_PATH, {
    method: "PUT",
    json: patch,
  });
}

export function reportStreamUrl(): string {
  return REPORT_PATH;
}

export function chatStreamUrl(): string {
  return CHAT_PATH;
}
