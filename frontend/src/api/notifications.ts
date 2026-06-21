import { fetchJson } from "./client";

export interface UnreadResponse {
  total: number;
  by_department: Record<string, number>;
}

export async function getUnread(): Promise<UnreadResponse> {
  return fetchJson<UnreadResponse>("/api/notifications/unread");
}

export async function markRead(department: string): Promise<{ marked_read: number }> {
  return fetchJson<{ marked_read: number }>("/api/notifications/read", {
    method: "POST",
    json: { department },
  });
}
