import { fetchJson } from "./client";

export type Department = "secretary" | "equity_research";
export type MessageRole = "user" | "assistant" | "system" | "tool";

export interface ChatSession {
  id: string;
  department: Department;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  tool_calls: unknown[] | null;
  model_ref: string | null;
  token_usage: Record<string, unknown> | null;
  created_at: string;
}

export const listSessions = (includeArchived = false) =>
  fetchJson<{ items: ChatSession[] }>(
    `/api/chat/sessions${includeArchived ? "?include_archived=true" : ""}`,
  );

export const createSession = (body: { department: Department; title: string }) =>
  fetchJson<ChatSession>("/api/chat/sessions", { method: "POST", json: body });

export const patchSession = (
  id: string,
  patch: { title?: string; pinned?: boolean; archived?: boolean },
) => fetchJson<{ ok: true }>(`/api/chat/sessions/${id}`, { method: "PATCH", json: patch });

export const deleteSession = (id: string) =>
  fetchJson<void>(`/api/chat/sessions/${id}`, { method: "DELETE" });

export const listMessages = (sessionId: string) =>
  fetchJson<{ items: ChatMessage[] }>(`/api/chat/sessions/${sessionId}/messages`);
