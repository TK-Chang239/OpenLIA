import { useMemo, useState } from "react";
import { ChevronLeft, Plus, Trash2 } from "lucide-react";
import { MCPInfoCard } from "./MCPInfoCard";
import { createConnector } from "../../api/connectors";
import type { Category, CreateConnectorInput, LaunchSpec } from "../../api/connectors";
import { builtinsForCategory } from "../../api/builtins";

type Method = "built_in" | "remote_mcp" | "cli_mcp";

interface EnvRow {
  key: string;
  value: string;
}

interface Draft {
  method: Method;
  builtinTemplate: string;
  apiKey: string;
  remoteUrl: string;
  remoteAuth: string;
  remoteProviderId: string;
  cliProviderId: string;
  cliArgv: string;
  cliEnv: EnvRow[];
}

const EMPTY_DRAFT: Draft = {
  method: "built_in",
  builtinTemplate: "",
  apiKey: "",
  remoteUrl: "",
  remoteAuth: "",
  remoteProviderId: "",
  cliProviderId: "",
  cliArgv: "",
  cliEnv: [],
};

const METHOD_LABEL: Record<Method, string> = {
  built_in: "Built-in",
  remote_mcp: "Remote MCP",
  cli_mcp: "CLI install",
};

function deriveProviderIdFromUrl(url: string): string {
  try {
    const u = new URL(url);
    return u.hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export function AddProviderForm({
  category,
  onCancel,
  onSaved,
}: {
  category: Category;
  onCancel: () => void;
  onSaved: (testError?: string | null) => void;
}) {
  // Each open of this form starts with a clean draft — drafts are NOT
  // persisted between attempts. The user expects an empty form every time
  // they click "Add provider".
  const [draft, setDraft] = useState<Draft>(EMPTY_DRAFT);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = <K extends keyof Draft>(key: K, value: Draft[K]) =>
    setDraft((d) => ({ ...d, [key]: value }));

  const builtins = useMemo(() => builtinsForCategory(category), [category]);

  const updateEnvRow = (idx: number, patch: Partial<EnvRow>) =>
    setDraft((d) => ({
      ...d,
      cliEnv: d.cliEnv.map((row, i) => (i === idx ? { ...row, ...patch } : row)),
    }));

  const addEnvRow = () =>
    setDraft((d) => ({ ...d, cliEnv: [...d.cliEnv, { key: "", value: "" }] }));

  const removeEnvRow = (idx: number) =>
    setDraft((d) => ({ ...d, cliEnv: d.cliEnv.filter((_, i) => i !== idx) }));

  const buildPayload = (): { input: CreateConnectorInput } | { error: string } => {
    if (draft.method === "built_in") {
      if (!draft.builtinTemplate) return { error: "Please select a built-in provider." };
      const launch: LaunchSpec = {
        kind: "built_in",
        template_id: draft.builtinTemplate,
      };
      const input: CreateConnectorInput = {
        provider_id: draft.builtinTemplate,
        source: "built_in",
        category,
        launch,
      };
      // Personal-mode hosted demo: send the raw API key as credentials_ref.
      // The server stores it via the existing wizard secret-store path.
      if (draft.apiKey.trim()) input.credentials_ref = draft.apiKey.trim();
      return { input };
    }
    if (draft.method === "remote_mcp") {
      const url = draft.remoteUrl.trim();
      if (!url) return { error: "Remote MCP server URL is required." };
      const headers: Record<string, string> = {};
      if (draft.remoteAuth.trim()) headers["Authorization"] = draft.remoteAuth.trim();
      const launch: LaunchSpec = {
        kind: "remote_mcp",
        url,
        ...(Object.keys(headers).length > 0 ? { headers } : {}),
      };
      const providerId = draft.remoteProviderId.trim() || deriveProviderIdFromUrl(url) || url;
      return {
        input: {
          provider_id: providerId,
          source: "remote_mcp",
          category,
          launch,
        },
      };
    }
    // cli_mcp
    const providerId = draft.cliProviderId.trim();
    if (!providerId) return { error: "Provider ID is required for a CLI install." };
    const argv = draft.cliArgv.trim().split(/\s+/).filter(Boolean);
    if (argv.length === 0) return { error: "argv is required for a CLI install." };
    const env: Record<string, string> = {};
    for (const row of draft.cliEnv) {
      const k = row.key.trim();
      if (!k) continue;
      env[k] = row.value;
    }
    const launch: LaunchSpec = {
      kind: "cli_mcp",
      argv,
      ...(Object.keys(env).length > 0 ? { env } : {}),
    };
    return {
      input: {
        provider_id: providerId,
        source: "cli_mcp",
        category,
        launch,
      },
    };
  };

  const onSave = async () => {
    setLoading(true);
    setError(null);

    const built = buildPayload();
    if ("error" in built) {
      setError(built.error);
      setLoading(false);
      return;
    }

    try {
      const result = await createConnector(built.input);
      if (result.status === "failed") {
        const message = result.last_error || "Provider test failed. Check your inputs and try again.";
        setError(message);
        onSaved(message);
        return;
      }
      onSaved(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to add provider.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button
        type="button"
        onClick={onCancel}
        className="inline-flex items-center gap-1 text-sm text-[--color-text-secondary] mb-3"
      >
        <ChevronLeft size={14} />
        Back to list
      </button>
      <h3 className="text-lg font-semibold text-[--color-text-primary] mb-4">
        Add {category.replace("_", " ")} provider
      </h3>
      <div role="radiogroup" aria-label="Connector method" className="flex flex-col gap-2 mb-5">
        {(Object.keys(METHOD_LABEL) as Method[]).map((m) => (
          <label
            key={m}
            className={`flex items-center gap-2 px-3 py-2 rounded-[--radius-md] border cursor-pointer ${
              draft.method === m
                ? "border-[--color-accent-primary] bg-[--color-surface-hover]"
                : "border-[--color-border-subtle]"
            }`}
          >
            <input
              type="radio"
              name="connector-method"
              value={m}
              checked={draft.method === m}
              onChange={() => update("method", m)}
            />
            <span className="text-sm text-[--color-text-primary]">{METHOD_LABEL[m]}</span>
          </label>
        ))}
      </div>

      {draft.method === "built_in" ? (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">Provider</span>
            <select
              value={draft.builtinTemplate}
              onChange={(e) => update("builtinTemplate", e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            >
              <option value="">Please select a provider</option>
              {builtins.map((opt) => (
                <option key={opt.template_id} value={opt.template_id}>
                  {opt.display_name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">API key</span>
            <input
              type="password"
              value={draft.apiKey}
              onChange={(e) => update("apiKey", e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          {builtins.length === 0 ? (
            <p className="text-xs text-[--color-text-secondary] mb-5">
              No built-in templates for this category. Try <strong>Remote MCP</strong> or{" "}
              <strong>CLI install</strong>.
            </p>
          ) : null}
        </>
      ) : draft.method === "remote_mcp" ? (
        <>
          <MCPInfoCard />
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Provider ID
              <span className="text-[--color-text-secondary] font-normal ml-2">
                (label, e.g. polygon)
              </span>
            </span>
            <input
              value={draft.remoteProviderId}
              onChange={(e) => update("remoteProviderId", e.target.value)}
              placeholder="polygon"
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Remote MCP server URL <span className="text-[--color-feedback-error]">*</span>
            </span>
            <input
              value={draft.remoteUrl}
              onChange={(e) => update("remoteUrl", e.target.value)}
              placeholder="https://example.com/mcp"
              required
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Bearer token / Authorization header
              <span className="text-[--color-text-secondary] font-normal ml-2">(optional)</span>
            </span>
            <input
              value={draft.remoteAuth}
              onChange={(e) => update("remoteAuth", e.target.value)}
              placeholder="Bearer sk_…"
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
        </>
      ) : (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Provider ID <span className="text-[--color-feedback-error]">*</span>
            </span>
            <input
              value={draft.cliProviderId}
              onChange={(e) => update("cliProviderId", e.target.value)}
              placeholder="my-mcp-server"
              required
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              argv <span className="text-[--color-feedback-error]">*</span>
              <span className="text-[--color-text-secondary] font-normal ml-2">
                (whitespace-separated)
              </span>
            </span>
            <input
              value={draft.cliArgv}
              onChange={(e) => update("cliArgv", e.target.value)}
              placeholder="npx -y my-mcp-server"
              required
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm font-mono"
            />
          </label>
          <div className="mb-5">
            <span className="text-sm font-medium text-[--color-text-primary] block mb-2">
              Environment variables
              <span className="text-[--color-text-secondary] font-normal ml-2">(optional)</span>
            </span>
            <ul className="flex flex-col gap-2">
              {draft.cliEnv.map((row, idx) => (
                <li key={idx} className="flex items-center gap-2">
                  <input
                    aria-label={`env key ${idx}`}
                    value={row.key}
                    onChange={(e) => updateEnvRow(idx, { key: e.target.value })}
                    placeholder="KEY"
                    className="h-9 px-2 flex-1 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm font-mono"
                  />
                  <input
                    aria-label={`env value ${idx}`}
                    value={row.value}
                    onChange={(e) => updateEnvRow(idx, { value: e.target.value })}
                    placeholder="value"
                    className="h-9 px-2 flex-1 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm font-mono"
                  />
                  <button
                    type="button"
                    aria-label={`remove env ${idx}`}
                    onClick={() => removeEnvRow(idx)}
                    className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
                  >
                    <Trash2 size={14} />
                  </button>
                </li>
              ))}
            </ul>
            <button
              type="button"
              onClick={addEnvRow}
              className="inline-flex items-center gap-1 text-sm text-[--color-text-secondary] mt-2"
            >
              <Plus size={12} />
              Add env var
            </button>
          </div>
        </>
      )}

      {error ? <p className="text-sm text-[--color-feedback-error] mb-3">{error}</p> : null}
      <div className="flex justify-end gap-2 mt-6">
        <button
          type="button"
          onClick={onCancel}
          className="h-9 px-3 rounded-[--radius-md] text-sm text-[--color-text-secondary]"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onSave}
          disabled={loading}
          className="h-9 px-3 rounded-[--radius-md] text-sm bg-[--color-accent-primary] text-white"
        >
          {loading ? "Testing…" : "Test & Save"}
        </button>
      </div>
    </div>
  );
}
