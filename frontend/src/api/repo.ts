import { fetchJson } from "./client";

export interface RepoItem {
  id: string;
  report_id: string;
  created_at: string;
}

export interface RepoRow {
  id: string;
  report_id: string;
  department: string;
  title: string;
  filename: string;
  generated_at: string;
  saved_at: string;
}

export interface RepoFilteredList {
  items: RepoRow[];
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface RepoFacets {
  departments: { slug: string; count: number }[];
  total: number;
}

export type RepoSort =
  | "saved_desc"
  | "saved_asc"
  | "generated_desc"
  | "generated_asc"
  | "department_asc"
  | "filename_asc";

export interface RepoListParams {
  q?: string;
  departments?: string[];
  generated_from?: string;
  generated_to?: string;
  saved_from?: string;
  saved_to?: string;
  sort?: RepoSort;
  page?: number;
  page_size?: number;
}

export const listRepoItems = () => fetchJson<{ items: RepoItem[] }>("/api/repo/items");

export const listRepoItemsFiltered = (params: RepoListParams = {}): Promise<RepoFilteredList> => {
  const qs = new URLSearchParams();
  qs.set("filtered", "true");
  if (params.q) qs.set("q", params.q);
  if (params.departments && params.departments.length > 0) {
    qs.set("department", params.departments.join(","));
  }
  if (params.generated_from) qs.set("generated_from", params.generated_from);
  if (params.generated_to) qs.set("generated_to", params.generated_to);
  if (params.saved_from) qs.set("saved_from", params.saved_from);
  if (params.saved_to) qs.set("saved_to", params.saved_to);
  if (params.sort) qs.set("sort", params.sort);
  if (params.page !== undefined) qs.set("page", String(params.page));
  if (params.page_size !== undefined) qs.set("page_size", String(params.page_size));
  return fetchJson<RepoFilteredList>(`/api/repo/items?${qs.toString()}`);
};

export const fetchRepoFacets = () => fetchJson<RepoFacets>("/api/repo/facets");

export const saveToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/items", { method: "POST", json: { report_id: reportId } });

export const unsaveFromRepo = (reportId: string) =>
  fetchJson<void>(`/api/repo/items?report_id=${reportId}`, { method: "DELETE" });

/** Alias used by Equity Research ReportCard.onSave (NEW-14-05). */
export const saveReportToRepo = (reportId: string) => saveToRepo(reportId);
