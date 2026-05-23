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

// v2.2 pipeline-run mirrors of the v1 save/unsave/list helpers. The
// backend stores both kinds of saves in repo_items via a polymorphic
// pointer (report_id XOR pipeline_run_id); the frontend keeps the
// surfaces separate so callers stay explicit about which engine wrote
// the artifact.

export const saveV2RunToRepo = (runId: string) =>
  fetchJson<RepoItem>("/api/repo/v2-runs", {
    method: "POST",
    json: { pipeline_run_id: runId },
  });

export const unsaveV2RunFromRepo = (runId: string) =>
  fetchJson<void>(
    `/api/repo/v2-runs?pipeline_run_id=${encodeURIComponent(runId)}`,
    { method: "DELETE" },
  );

/** Returns the v2.2 pipeline_run ids the current user has saved.
 *  SavedReportsContext fetches this on mount so the v2 ReportCard's
 *  `initialSaved` prop is correct after a reload. */
export const listSavedV2Runs = () =>
  fetchJson<{ saved_run_ids: string[] }>("/api/repo/v2-runs");

export const deleteV2Run = (runId: string) =>
  fetchJson<void>(
    `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}`,
    { method: "DELETE" },
  );

export interface V2RunMeta {
  id: string;
  state: string;
  deleted_at: string | null;
  expired_at: string | null;
  created_at: string | null;
  has_report: boolean;
  title: string | null;
  ticker: string | null;
}

export const fetchV2RunMeta = (runId: string) =>
  fetchJson<V2RunMeta>(
    `/api/departments/equity-research/v2/runs/${encodeURIComponent(runId)}/meta`,
  );
