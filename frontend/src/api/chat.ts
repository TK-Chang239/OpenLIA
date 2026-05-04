import { fetchJson } from "./client";
import type { DepartmentSlug } from "./departments";

export type { DepartmentSlug } from "./departments";
// Back-compat alias for existing call sites; new code should prefer DepartmentSlug.
export type Department = DepartmentSlug;

export type MessageRole = "user" | "assistant" | "system" | "tool";

export interface ChatSession {
  id: string;
  department: DepartmentSlug;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  created_at: string;
  model_id?: string | null;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls: unknown[] | null;
  model_ref: string | null;
  token_usage: Record<string, unknown> | null;
  created_at: string;
  stopped_at?: string | null;
}

export interface ListSessionsOptions {
  department?: DepartmentSlug;
  include_archived?: boolean;
  q?: string;
}

export const listSessions = (opts: ListSessionsOptions = {}) => {
  const params = new URLSearchParams();
  if (opts.department) params.set("department", opts.department);
  if (opts.include_archived) params.set("include_archived", "true");
  if (opts.q) params.set("q", opts.q);
  const qs = params.toString();
  return fetchJson<{ items: ChatSession[] }>(
    `/api/chat/sessions${qs ? `?${qs}` : ""}`,
  );
};

export const createSession = (body: { department: DepartmentSlug; title: string }) =>
  fetchJson<ChatSession>("/api/chat/sessions", { method: "POST", json: body });

export const patchSession = (
  id: string,
  patch: { title?: string; pinned?: boolean; archived?: boolean },
) => fetchJson<{ ok: true }>(`/api/chat/sessions/${id}`, { method: "PATCH", json: patch });

export const deleteSession = (id: string) =>
  fetchJson<void>(`/api/chat/sessions/${id}`, { method: "DELETE" });

export const setSessionModel = (id: string, model_id: string | null) =>
  fetchJson<{ ok: true }>(`/api/chat/sessions/${id}/model`, {
    method: "PUT",
    json: { model_id },
  });

export const listMessages = (sessionId: string) =>
  fetchJson<{ items: ChatMessage[] }>(`/api/chat/sessions/${sessionId}/messages`);

export const getDefaultSessionForDepartment = (department: DepartmentSlug) =>
  fetchJson<ChatSession>(`/api/chat/sessions/by-department/${department}`);
