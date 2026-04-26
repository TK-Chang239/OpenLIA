import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { MCPInfoCard } from "./MCPInfoCard";
import { addProvider } from "../../api/setup";
import type { ProviderEntry } from "../../api/setup";

type Mode = "builtin" | "mcp" | "config";
type Category = "financial" | "news" | "social" | "web_search";

const PLACEHOLDER = "";

const BUILTIN_CATALOG: Record<Category, { value: string; label: string }[]> = {
  financial: [
    { value: "eodhd", label: "EODHD" },
    { value: "fmp", label: "Financial Modeling Prep" },
    { value: "finnhub", label: "Finnhub" },
  ],
  news: [
    { value: "newsapi_ai", label: "News API AI" },
    { value: "mediastack", label: "Mediastack" },
  ],
  social: [
    { value: "reddit", label: "Reddit" },
    { value: "x", label: "X / Twitter" },
  ],
  web_search: [
    { value: "brave", label: "Brave Search" },
    { value: "tavily", label: "Tavily" },
    { value: "serper", label: "Serper" },
    { value: "firecrawl", label: "Firecrawl" },
  ],
};

interface Draft {
  mode: Mode;
  builtinProvider: string;
  apiKey: string;
  mcpName: string;
  mcpUrl: string;
  mcpAuth: string;
  oauthClientId: string;
  oauthClientSecret: string;
  configJson: string;
}

const CONFIG_PLACEHOLDER = `{
  "mode": "builtin",
  "provider": "newsapi_ai",
  "api_key": "your_api_key_here"
}`;

const EMPTY_DRAFT: Draft = {
  mode: "builtin",
  builtinProvider: PLACEHOLDER,
  apiKey: "",
  mcpName: "",
  mcpUrl: "",
  mcpAuth: "",
  oauthClientId: "",
  oauthClientSecret: "",
  configJson: "",
};

function parseConfigJson(raw: string): { entry: ProviderEntry } | { error: string } {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    return { error: err instanceof Error ? `Invalid JSON: ${err.message}` : "Invalid JSON." };
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { error: "Config must be a JSON object." };
  }
  const obj = parsed as Record<string, unknown>;
  const mode = obj.mode;
  if (mode !== "builtin" && mode !== "mcp") {
    return { error: 'Field "mode" must be "builtin" or "mcp".' };
  }
  const entry: ProviderEntry = { mode };
  if (typeof obj.provider === "string") entry.provider = obj.provider;
  if (typeof obj.api_key === "string") entry.api_key = obj.api_key;
  if (typeof obj.mcp_url === "string") entry.mcp_url = obj.mcp_url;
  if (typeof obj.mcp_auth_header === "string") entry.mcp_auth_header = obj.mcp_auth_header;
  if (typeof obj.oauth_client_id === "string") entry.oauth_client_id = obj.oauth_client_id;
  if (typeof obj.oauth_client_secret === "string")
    entry.oauth_client_secret = obj.oauth_client_secret;
  return { entry };
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

  const onSave = async () => {
    setLoading(true);
    setError(null);

    let entry: ProviderEntry;
    if (draft.mode === "builtin") {
      if (!draft.builtinProvider) {
        setError("Please select a provider.");
        setLoading(false);
        return;
      }
      entry = {
        mode: "builtin",
        provider: draft.builtinProvider,
        api_key: draft.apiKey,
      };
    } else if (draft.mode === "mcp") {
      if (!draft.mcpUrl.trim()) {
        setError("Remote MCP server URL is required for a custom connector.");
        setLoading(false);
        return;
      }
      entry = {
        mode: "mcp",
        provider: draft.mcpName.trim() || undefined,
        mcp_url: draft.mcpUrl.trim(),
        mcp_auth_header: draft.mcpAuth || undefined,
        oauth_client_id: draft.oauthClientId.trim() || undefined,
        oauth_client_secret: draft.oauthClientSecret || undefined,
      };
    } else {
      // Standard config: user pastes a JSON object matching ProviderEntry.
      const parsed = parseConfigJson(draft.configJson);
      if ("error" in parsed) {
        setError(parsed.error);
        setLoading(false);
        return;
      }
      entry = parsed.entry;
    }

    try {
      const result = await addProvider({ category, entry });
      if (!result.ok) {
        const message =
          result.error || "Provider test failed. Check your inputs and try again.";
        setError(message);
        onSaved(message);
        return;
      }
      onSaved(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add provider.");
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
      <div className="flex p-1 bg-[--color-surface-hover] rounded-[--radius-md] w-fit mb-5">
        {(["builtin", "mcp", "config"] as Mode[]).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => update("mode", m)}
            className={`px-3 py-1.5 rounded-[--radius-sm] text-sm capitalize ${
              draft.mode === m ? "bg-[--color-bg-elevated] shadow-sm font-medium" : ""
            }`}
          >
            {m === "mcp"
              ? "Custom Connector"
              : m === "config"
                ? "Standard Config"
                : "Built-in"}
          </button>
        ))}
      </div>

      {draft.mode === "builtin" ? (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">Provider</span>
            <select
              value={draft.builtinProvider}
              onChange={(e) => update("builtinProvider", e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            >
              <option value={PLACEHOLDER}>Please select a provider</option>
              {BUILTIN_CATALOG[category].map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
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
          <p className="text-xs text-[--color-text-secondary] mb-5">
            Need a provider that isn't listed? Switch to <strong>Custom Connector</strong> and
            paste the provider's MCP server URL.
          </p>
        </>
      ) : draft.mode === "mcp" ? (
        <>
          <MCPInfoCard />
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Name
              <span className="text-[--color-text-secondary] font-normal ml-2">
                (label, e.g. polygon)
              </span>
            </span>
            <input
              value={draft.mcpName}
              onChange={(e) => update("mcpName", e.target.value)}
              placeholder="polygon"
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">
              Remote MCP server URL <span className="text-[--color-feedback-error]">*</span>
            </span>
            <input
              value={draft.mcpUrl}
              onChange={(e) => update("mcpUrl", e.target.value)}
              placeholder="https://example.com/mcp"
              required
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <details className="mb-5">
            <summary className="text-sm text-[--color-text-secondary] cursor-pointer">
              Advanced
            </summary>
            <label className="flex flex-col gap-1.5 mt-3">
              <span className="text-sm font-medium text-[--color-text-primary]">
                OAuth Client ID
                <span className="text-[--color-text-secondary] font-normal ml-2">(optional)</span>
              </span>
              <input
                value={draft.oauthClientId}
                onChange={(e) => update("oauthClientId", e.target.value)}
                placeholder="client_id"
                className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
              />
            </label>
            <label className="flex flex-col gap-1.5 mt-3">
              <span className="text-sm font-medium text-[--color-text-primary]">
                OAuth Client Secret
                <span className="text-[--color-text-secondary] font-normal ml-2">(optional)</span>
              </span>
              <input
                type="password"
                value={draft.oauthClientSecret}
                onChange={(e) => update("oauthClientSecret", e.target.value)}
                placeholder="client_secret"
                className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
              />
            </label>
            <label className="flex flex-col gap-1.5 mt-3">
              <span className="text-sm font-medium text-[--color-text-primary]">
                Auth header
                <span className="text-[--color-text-secondary] font-normal ml-2">
                  (optional, used if no OAuth credentials)
                </span>
              </span>
              <input
                value={draft.mcpAuth}
                onChange={(e) => update("mcpAuth", e.target.value)}
                placeholder="Bearer sk_…"
                className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
              />
            </label>
          </details>
        </>
      ) : (
        <>
          <p className="text-xs text-[--color-text-secondary] mb-3">
            Paste a JSON object matching the provider config schema. Useful when copying a
            known-good config across machines or sharing one with your team.
          </p>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">Provider config</span>
            <textarea
              value={draft.configJson}
              onChange={(e) => update("configJson", e.target.value)}
              placeholder={CONFIG_PLACEHOLDER}
              rows={10}
              spellCheck={false}
              className="px-3 py-2 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm font-mono"
            />
          </label>
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
