import { fetchJson } from "./client";

export type DepartmentStatus = "active" | "disabled";

export interface DepartmentHealth {
  department_id: string;
  status: DepartmentStatus;
  reason: string | null;
  missing_categories: string[];
  unresolved_needs: string[];
}

export const fetchDeptHealth = () =>
  fetchJson<DepartmentHealth[]>("/api/dept-health");

export const recheckDeptHealth = () =>
  fetchJson<DepartmentHealth[]>("/api/dept-health/refresh", { method: "POST" });
