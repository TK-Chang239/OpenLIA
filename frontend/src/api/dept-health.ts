import { fetchJson } from "./client";

export type DepartmentStatus = "active" | "disabled";

export interface DepartmentHealth {
  department_id: string;
  status: DepartmentStatus;
  reason: string | null;
  missing_categories: string[];
  unresolved_needs: string[];
  // Static dept-registry metadata + the unsatisfied subset of
  // `required_any_of`. Optional in the type because legacy responses
  // (and many test fixtures) predate these fields.
  required_categories?: string[];
  optional_categories?: string[];
  satisfied_categories?: string[];
  required_any_of?: string[][];
  unsatisfied_any_of?: string[][];
}

export const fetchDeptHealth = () =>
  fetchJson<DepartmentHealth[]>("/api/dept-health");

export const recheckDeptHealth = () =>
  fetchJson<DepartmentHealth[]>("/api/dept-health/refresh", { method: "POST" });
