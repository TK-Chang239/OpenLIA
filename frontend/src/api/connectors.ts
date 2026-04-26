import { fetchJson } from "./client";

export type Category = "financial" | "news" | "social" | "web_search";
export type ConnectorSource = "built_in" | "remote_mcp" | "cli_mcp";
export type ConnectorStatus = "pending" | "validated" | "failed";
export type CategoryStatus = "ok" | "missing" | "enhanced" | "basic";

export type LaunchSpec =
  | { kind: "built_in"; template_id: string }
  | { kind: "remote_mcp"; url: string; headers?: Record<string, string> }
  | { kind: "cli_mcp"; argv: string[]; env?: Record<string, string> };

export interface ConnectorRow {
  id: string;
  provider_id: string;
  source: ConnectorSource;
  category: Category;
  status: ConnectorStatus;
  last_error: string | null;
  cached_tools_count: number;
}

export interface CreateConnectorInput {
  provider_id: string;
  source: ConnectorSource;
  category: Category;
  launch: LaunchSpec;
  credentials_ref?: string;
}

export interface ScopeResponseRow {
  connector_id: string;
  rows_written: number;
}

export interface ScopeResponse {
  scoped: number;
  per_connector: ScopeResponseRow[];
}

export interface ReviewCategoryRow {
  category: Category;
  required: boolean;
  status: CategoryStatus;
  tool_count: number;
  providers: string[];
}

export interface ReviewDepartmentRow {
  department_id: string;
  ready: boolean;
  categories: ReviewCategoryRow[];
}

export interface ReviewResponse {
  departments: ReviewDepartmentRow[];
}

export const listConnectors = () =>
  fetchJson<ConnectorRow[]>("/api/connectors");

export const createConnector = (input: CreateConnectorInput) =>
  fetchJson<ConnectorRow>("/api/connectors", {
    method: "POST",
    json: input,
  });

export const deleteConnector = async (id: string): Promise<void> => {
  await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
};

export const revalidateConnector = (id: string) =>
  fetchJson<ConnectorRow>(
    `/api/connectors/${encodeURIComponent(id)}/validate`,
    { method: "POST" },
  );

export const scopeAll = (connectorIds?: string[]) =>
  fetchJson<ScopeResponse>("/api/connectors/review/scope", {
    method: "POST",
    json: { connector_ids: connectorIds ?? null },
  });

export const getReview = () =>
  fetchJson<ReviewResponse>("/api/connectors/review");
