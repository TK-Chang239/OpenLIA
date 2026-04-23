import { fetchJson } from "./client";

export interface RepoItem {
  id: string;
  report_id: string;
  created_at: string;
}

export const listRepoItems = () => fetchJson<{ items: RepoItem[] }>("/api/repo/items");

export const saveToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/items", { method: "POST", json: { report_id: reportId } });

export const unsaveFromRepo = (reportId: string) =>
  fetchJson<void>(`/api/repo/items?report_id=${reportId}`, { method: "DELETE" });
