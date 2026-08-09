import { fetchJson } from "./client";

const BASE = "/api/departments/panic_thermometer";

export type PanelId =
  | "oil"
  | "inflation"
  | "fed_language"
  | "wage_growth"
  | "diplomacy";

export type PanelStatus =
  | "green"
  | "amber"
  | "red"
  | "dark_red"
  | "disabled";

export type CompositeLevel =
  | "calm"
  | "elevated"
  | "high"
  | "severe"
  | "crisis";

export interface PanelRule {
  status: PanelStatus;
  formula: string;
  label: string;
}

export interface ManualOverride {
  status: PanelStatus;
  note?: string | null;
  set_at: string;
}

export interface PanelConfig {
  panel_id: PanelId;
  rules: PanelRule[];
  params: Record<string, unknown>;
  streak_condition: string | null;
  manual_override: ManualOverride | null;
  milestone_date: string | null;
  enabled?: boolean;
}

export interface CompositeSettings {
  mode: "count" | "weighted";
  red_threshold?: number;
  weights?: Record<string, number>;
  thresholds?: Record<string, number>;
  refresh_interval_minutes?: number;
}

export interface UserConfig {
  id: string;
  panel_config: PanelConfig[];
  composite_settings: CompositeSettings;
  active_preset_id: string | null;
}

export interface PanelResult {
  panel_id: PanelId;
  status: PanelStatus;
  label: string;
  resolved_values: Record<string, unknown>;
  derived_scalars: Record<string, unknown>;
  // Full panel scalar readings (survey levels, matched headlines, keyword
  // flags, day counts, ...).
  extras: Record<string, unknown>;
  // Named numeric arrays (price/tip/value series) that back the charts.
  raw_series: Record<string, number[]>;
  // Effective panel params (thresholds, targets, tickers) for the viewer.
  params: Record<string, unknown>;
  warnings: string[];
}

export interface CompositeResult {
  level: CompositeLevel;
  score: number;
  red_count: number;
  mode: string;
}

export interface DashboardPayload {
  panels: Record<PanelId, PanelResult>;
  composite: CompositeResult;
  generated_at: string;
  warnings: string[];
}

export interface PtPreset {
  id: string;
  user_id: string | null;
  name: string;
  description: string | null;
  is_shipped: boolean;
}

export interface FormulaParseResponse {
  ok: boolean;
  identifiers?: string[];
  unknown_identifiers?: string[];
  warnings?: string[];
  errors?: Array<{ type: string; message: string; position?: number }>;
}

export interface FormulaTestResponse {
  value: number | boolean | null;
  resolved_values: Record<string, unknown>;
  errors: Array<{ type: string; message: string }>;
  warnings: string[];
}

export interface RulesetPreviewResponse {
  status: PanelStatus;
  matched_rule_index: number;
  label: string;
  resolved_values: Record<string, unknown>;
  derived_scalars: Record<string, unknown>;
  warnings: string[];
}

export function fetchDashboard(): Promise<DashboardPayload> {
  return fetchJson<DashboardPayload>(`${BASE}/dashboard`);
}

export function fetchConfig(): Promise<UserConfig> {
  return fetchJson<UserConfig>(`${BASE}/config`);
}

export function saveConfig(
  cfg: Pick<UserConfig, "panel_config" | "composite_settings">,
): Promise<UserConfig> {
  return fetchJson<UserConfig>(`${BASE}/config`, {
    method: "PUT",
    json: cfg,
  });
}

export function listPresets(): Promise<PtPreset[]> {
  return fetchJson<PtPreset[]>(`${BASE}/presets`);
}

export function createPreset(
  name: string,
  description: string | null,
): Promise<PtPreset> {
  return fetchJson<PtPreset>(`${BASE}/presets`, {
    method: "POST",
    json: { name, description },
  });
}

export function updatePreset(
  id: string,
  payload: { name: string; description: string | null },
): Promise<PtPreset> {
  return fetchJson<PtPreset>(`${BASE}/presets/${id}`, {
    method: "PUT",
    json: payload,
  });
}

export function deletePreset(id: string): Promise<null> {
  return fetchJson<null>(`${BASE}/presets/${id}`, { method: "DELETE" });
}

export function applyPreset(id: string): Promise<UserConfig> {
  return fetchJson<UserConfig>(`${BASE}/presets/${id}/apply`, {
    method: "POST",
  });
}

export function exportConfig(): Promise<{
  version: number;
  panel_config: PanelConfig[];
  composite_settings: CompositeSettings;
}> {
  return fetchJson(`${BASE}/config/export`);
}

export function importConfig(payload: unknown): Promise<UserConfig> {
  return fetchJson<UserConfig>(`${BASE}/config/import`, {
    method: "POST",
    json: payload,
  });
}

export function parseFormula(
  formula: string,
  panel: PanelId,
): Promise<FormulaParseResponse> {
  return fetchJson<FormulaParseResponse>(`${BASE}/formula/parse`, {
    method: "POST",
    json: { formula, panel },
  });
}

export function testFormula(
  formula: string,
  panel: PanelId,
  params: Record<string, unknown>,
): Promise<FormulaTestResponse> {
  return fetchJson<FormulaTestResponse>(`${BASE}/formula/test`, {
    method: "POST",
    json: { formula, panel, params },
  });
}

export function previewRuleset(
  panel: PanelId,
  ruleset: {
    rules: PanelRule[];
    params: Record<string, unknown>;
    streak_condition: string | null;
  },
): Promise<RulesetPreviewResponse> {
  return fetchJson<RulesetPreviewResponse>(`${BASE}/ruleset/preview`, {
    method: "POST",
    json: { panel, ruleset },
  });
}
