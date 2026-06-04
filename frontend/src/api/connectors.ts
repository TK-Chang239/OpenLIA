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
  grounding_paths?: string[] | null;
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
  grounding_paths?: string[] | null;
  openapi_url?: string | null;
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

export const syncTemplateSpecs = (id: string) =>
  fetchJson<{ inserted: number }>(
    `/api/connectors/${encodeURIComponent(id)}/sync-template-specs`,
    { method: "POST" },
  );

// Backward-compatible alias used by older callers.
export const revalidateConnector = validateConnector;

export interface BuiltinTemplate {
  template_id: string;
  display_name: string;
  category: Category;
  api_key_env_var: string;
  covered_need_ids: string[];
}

export interface InstallBuiltinInput {
  template_id: string;
  api_key: string;
}

export const listBuiltinTemplates = (): Promise<BuiltinTemplate[]> =>
  fetchJson<BuiltinTemplate[]>("/api/connectors/builtins");

export const installBuiltin = (input: InstallBuiltinInput): Promise<ConnectorRow> =>
  fetchJson<ConnectorRow>("/api/connectors/install-builtin", {
    method: "POST",
    json: input,
  });
