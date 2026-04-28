import { fetchJson } from "./client";

export type Mode = "personal" | "company";

export interface WizardStatus {
  mode: Mode;
  wizard_completed: boolean;
  current_step: string;
  completed_steps: string[];
  env_overrides: Record<string, string>;
}

export interface TestResult {
  ok: boolean;
  latency_ms: number | null;
  error: string | null;
}

export interface TierEntry {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
  capabilities?: Record<string, boolean>;
  is_tier_default?: boolean;
}

export interface ModelsPayload {
  thinking: TierEntry[];
  everyday: TierEntry[];
  quick: TierEntry[];
}

export interface ReviewPoll {
  state: "running" | "complete" | "failed";
  progress: number;
  result: unknown | null;
  error: string | null;
}

export interface AccessControlPayload {
  signup_policy: "invite_only" | "closed";
  allowed_domains?: string;
  bind_host: string;
  bind_port: number;
}

export const getStatus = () => fetchJson<WizardStatus>("/api/setup/status");

export const setMode = (mode: Mode) =>
  fetchJson<{ mode: Mode }>("/api/setup/mode", { method: "POST", json: { mode } });

export const takeover = () =>
  fetchJson<{ ok: boolean }>("/api/setup/takeover", { method: "POST" });

export const setIdentity = (displayName: string) =>
  fetchJson<{ display_name: string }>("/api/setup/identity", {
    method: "POST",
    json: { display_name: displayName },
  });

export const setAdmin = (payload: { email: string; password: string; display_name: string }) =>
  fetchJson<{ email: string }>("/api/setup/admin", { method: "POST", json: payload });

export const testModel = (payload: {
  provider: string;
  model: string;
  api_key?: string;
  base_url?: string;
}) => fetchJson<TestResult>("/api/setup/models/test", { method: "POST", json: payload });

export const saveModels = (payload: ModelsPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/models", { method: "POST", json: payload });

export const setAccessControl = (payload: AccessControlPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/access_control", { method: "POST", json: payload });

export const runReview = () =>
  fetchJson<{ review_id: string }>("/api/setup/review/run", { method: "POST" });

export const pollReview = (id: string) => fetchJson<ReviewPoll>(`/api/setup/review/${id}`);

export const finish = () =>
  fetchJson<{ redirect: string; mode: Mode }>("/api/setup/finish", { method: "POST" });

export const getRequiredTiers = () =>
  fetchJson<{ required_tiers: string[]; enabled_departments: string[] }>(
    "/api/setup/required_tiers",
  );
