import { fetchJson } from "./client";

export interface RepoItem {
  id: string;
  report_id: string;
  created_at: string;
}

/** Which engine wrote the saved report.
 *
 *   - "v1" — legacy ``reports.id`` rows. Open via FileViewer
 *     source ``{kind: "report"}``; delete via ``deleteReport``;
 *     repo state lives in ``SavedReportsContext.isSaved``.
 *   - "v3" — new equity-research engine (``report_v3.id``). Open
 *     via ``{kind: "v3_report"}``; delete via ``deleteV3Run``;
 *     repo state lives in ``SavedReportsContext.isV3Saved``.
 *
 *   - "eu_v2" — Earnings Update v2 engine (``eu_v2_report.id``).
 *     Open via ``{kind: "eu_v2_report"}``; repo state lives in
 *     ``SavedReportsContext.isEuSaved``.
 *
 *   - "mb_v2" — Morning Briefing engine (``report_mb.id``). Open
 *     via ``{kind: "mb_report"}``; repo state lives in
 *     ``SavedReportsContext.isMbSaved``.
 *
 *  v2.2 still lists via its own ``/repo/v2-runs`` surface; pending
 *  fanout follow-up. */
export type RepoEngine = "v1" | "v3" | "eu_v2" | "mb_v2";

export interface RepoRow {
  id: string;
  engine: RepoEngine;
  /** Id of the target row in its engine's namespace. For v1 this
   *  is reports.id; for v3 this is report_v3.id. Branch on
   *  ``engine`` to know how to dereference it. */
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

// v3 equity-research repo mirrors of the v1/v2 helpers. Polymorphic
// pointer column ``v3_report_id`` lives in ``repo_items`` alongside
// ``report_id`` (v1) and ``pipeline_run_id`` (v2.2); the routes keep
// each engine's surface explicit so callers stay clear about which
// engine wrote the artifact.

export const saveV3RunToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/v3-runs", {
    method: "POST",
    json: { v3_report_id: reportId },
  });

export const unsaveV3RunFromRepo = (reportId: string) =>
  fetchJson<void>(
    `/api/repo/v3-runs?v3_report_id=${encodeURIComponent(reportId)}`,
    { method: "DELETE" },
  );

/** Returns the v3 report ids the current user has saved.
 *  SavedReportsContext fetches this on mount so the V3ReportCard's
 *  `initialSaved` prop is correct after a reload. */
export const listSavedV3Runs = () =>
  fetchJson<{ saved_report_ids: string[] }>("/api/repo/v3-runs");

// Earnings Update v2 repo mirrors of the v3 helpers. Polymorphic
// pointer column ``eu_v2_report_id`` lives in ``repo_items`` alongside
// the v1/v2/v3 pointers; the routes keep each engine's surface explicit
// so callers stay clear about which engine wrote the artifact.

export const saveEuRunToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/eu-runs", {
    method: "POST",
    json: { eu_v2_report_id: reportId },
  });

export const unsaveEuRunFromRepo = (reportId: string) =>
  fetchJson<void>(
    `/api/repo/eu-runs?eu_v2_report_id=${encodeURIComponent(reportId)}`,
    { method: "DELETE" },
  );

/** Returns the EU v2 report ids the current user has saved. */
export const listSavedEuRuns = () =>
  fetchJson<{ saved_report_ids: string[] }>("/api/repo/eu-runs");

// Morning Briefing repo mirrors of the EU helpers. Polymorphic pointer
// column ``mb_v2_report_id`` lives in ``repo_items`` alongside the
// v1/v2/v3/eu pointers; the routes keep each engine's surface explicit.

export const saveMbRunToRepo = (reportId: string) =>
  fetchJson<RepoItem>("/api/repo/mb-runs", {
    method: "POST",
    json: { mb_v2_report_id: reportId },
  });

export const unsaveMbRunFromRepo = (reportId: string) =>
  fetchJson<void>(
    `/api/repo/mb-runs?mb_v2_report_id=${encodeURIComponent(reportId)}`,
    { method: "DELETE" },
  );

/** Returns the MB report ids the current user has saved. */
export const listSavedMbRuns = () =>
  fetchJson<{ saved_report_ids: string[] }>("/api/repo/mb-runs");
