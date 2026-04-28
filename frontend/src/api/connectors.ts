import { fetchJson } from "./client";

export type Category = "financial" | "news" | "social" | "web_search";
export type ConnectorSource = "built_in" | "remote_mcp" | "cli_mcp" | "python_lib" | "skill";
export type ConnectorStatus = "pending" | "validated" | "failed";

export interface ModeIn {
  kind: string;
  // cli_mcp
  argv?: string[];
  env_keys?: string[];
  // remote_mcp
  url?: string;
  headers?: Record<string, string>;
  // python_lib
  pip_name?: string;
  pip_version?: string;
  import_module?: string;
  instance_factory?: Record<string, unknown>;
}

export interface LaunchIn {
  modes: ModeIn[];
}

export interface ConnectorRow {
  id: string;
  provider_id: string;
  display_name: string;
  source: ConnectorSource;
  category: Category;
  status: ConnectorStatus;
  last_error: string | null;
  cached_tools_count: number;
}

export interface CreateConnectorInput {
  provider_id: string;
  display_name: string;
  source: ConnectorSource;
  category: Category;
  launch: LaunchIn;
  secrets?: Record<string, string>;
}

export interface ProposedSpec {
  department_id: string;
  need_id: string;
  proposed_spec: Record<string, unknown>;
  canary_value: unknown;
  canary_ok: boolean;
  shape_match: boolean;
  error: string | null;
}

export interface ApprovalOut {
  id: string;
  department_id: string;
  need_id: string;
  connector_id: string;
  access_mode: string;
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

export const validateConnector = (id: string) =>
  fetchJson<ConnectorRow>(
    `/api/connectors/${encodeURIComponent(id)}/validate`,
    { method: "POST" },
  );

// Backward-compatible alias used by older callers.
export const revalidateConnector = validateConnector;

export const listProposedSpecs = (connectorId: string) =>
  fetchJson<ProposedSpec[]>(
    `/api/connectors/${encodeURIComponent(connectorId)}/proposed-specs`,
  );

export const reResolveSpecs = (connectorId: string) =>
  fetchJson<ProposedSpec[]>(
    `/api/connectors/${encodeURIComponent(connectorId)}/proposed-specs/resolve`,
    { method: "POST" },
  );

export const approveSpec = (
  connectorId: string,
  departmentId: string,
  needId: string,
) =>
  fetchJson<ApprovalOut>(
    `/api/connectors/${encodeURIComponent(connectorId)}/proposed-specs/approve`,
    {
      method: "POST",
      json: { department_id: departmentId, need_id: needId },
    },
  );
