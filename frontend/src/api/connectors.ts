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

export type GroundingStatus = "none" | "pending" | "ready" | "failed";

export interface ConnectorDetail extends ConnectorRow {
  launch: LaunchIn;
  secret_keys: string[];
  source_repo_url?: string | null;
  source_repo_revision?: string | null;
  openapi_url?: string | null;
  grounding_status?: GroundingStatus;
  cached_repo_commit_sha?: string | null;
}

export interface CreateConnectorInput {
  provider_id: string;
  display_name: string;
  source: ConnectorSource;
  category: Category;
  launch: LaunchIn;
  secrets?: Record<string, string>;
  source_repo_url?: string | null;
  source_repo_revision?: string | null;
  openapi_url?: string | null;
}

export interface ProposedSpec {
  department_id: string;
  need_id: string;
  proposed_spec: Record<string, unknown>;
  canary_value: unknown;
  canary_ok: boolean;
  shape_match: boolean;
  error: string | null;
  connector_id?: string | null;
  unsatisfiable?: boolean;
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

export const getConnector = (id: string) =>
  fetchJson<ConnectorDetail>(`/api/connectors/${encodeURIComponent(id)}`);

export const updateConnector = (id: string, input: CreateConnectorInput) =>
  fetchJson<ConnectorRow>(`/api/connectors/${encodeURIComponent(id)}`, {
    method: "PUT",
    json: input,
  });

export interface IntrospectedParam {
  name: string;
  type: string | null;
  required: boolean;
  default: unknown;
}

export const introspectPythonLib = (importModule: string, cls: string) =>
  fetchJson<{ params: IntrospectedParam[] }>(
    "/api/connectors/introspect-python-lib",
    {
      method: "POST",
      json: { import_module: importModule, cls },
    },
  );

export const installPythonPackage = (pipName: string, pipVersion: string) =>
  fetchJson<{ stdout: string }>("/api/connectors/install-python-package", {
    method: "POST",
    json: { pip_name: pipName, pip_version: pipVersion },
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

export const listDeptProposedSpecs = (departmentId: string) =>
  fetchJson<ProposedSpec[]>(
    `/api/departments/${encodeURIComponent(departmentId)}/proposed-specs`,
  );

export const resolveDeptProposedSpecs = (departmentId: string) =>
  fetchJson<ProposedSpec[]>(
    `/api/departments/${encodeURIComponent(departmentId)}/proposed-specs/resolve`,
    { method: "POST" },
  );

export interface ResolveEvent {
  type: "tool_call";
  need_id: string;
  connector_id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export const listDeptResolveEvents = (departmentId: string) =>
  fetchJson<ResolveEvent[]>(
    `/api/departments/${encodeURIComponent(departmentId)}/proposed-specs/events`,
  );

export const resolveDeptNeed = (departmentId: string, needId: string) =>
  fetchJson<ProposedSpec>(
    `/api/departments/${encodeURIComponent(departmentId)}/proposed-specs/${encodeURIComponent(needId)}/resolve`,
    { method: "POST" },
  );

export const approveDeptSpec = (departmentId: string, needId: string) =>
  fetchJson<ApprovalOut>(
    `/api/departments/${encodeURIComponent(departmentId)}/proposed-specs/approve`,
    {
      method: "POST",
      json: { need_id: needId },
    },
  );
