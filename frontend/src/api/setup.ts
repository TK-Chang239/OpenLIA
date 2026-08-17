import { fetchJson } from "./client";

export type Mode = "personal" | "company";

export interface WizardStatus {
  mode: Mode;
  wizard_completed: boolean;
  current_step: string;
  completed_steps: string[];
  env_overrides: Record<string, string>;
}

export interface SaveModelsPayload {
  models: Array<{
    provider_kind: string;
    api_key: string | null;
    base_url: string | null;
    env_var_name: string | null;
    model_ref: string;
    display_name: string;
  }>;
  department_defaults: Record<string, string>;
  system_role_defaults: Record<string, string>;
}

export interface WizardSetupState {
  enabled_department_ids: string[];
  system_role_ids: string[];
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

export const saveModels = (payload: SaveModelsPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/models", { method: "POST", json: payload });

export const getSetupState = () =>
  fetchJson<WizardSetupState>("/api/setup/state");

export const saveProviders = () =>
  fetchJson<{ ok: boolean }>("/api/setup/providers", { method: "POST" });

export const setAccessControl = (payload: AccessControlPayload) =>
  fetchJson<{ ok: boolean }>("/api/setup/access_control", { method: "POST", json: payload });

export const finish = () =>
  fetchJson<{ redirect: string; mode: Mode }>("/api/setup/finish", { method: "POST" });
