import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { MCPInfoCard } from "./MCPInfoCard";
import { addProvider } from "../../api/setup";
import type { ProviderEntry } from "../../api/setup";

type Mode = "builtin" | "mcp" | "openapi";
type Category = "financial" | "news" | "social" | "web_search";

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
  ],
};

export function AddProviderForm({
  category,
  onCancel,
  onSaved,
}: {
  category: Category;
  onCancel: () => void;
  onSaved: (testError?: string | null) => void;
}) {
  const allowMcp = category !== "web_search";
  const [mode, setMode] = useState<Mode>("builtin");
  const [builtinProvider, setBuiltinProvider] = useState<string>(
    BUILTIN_CATALOG[category][0]?.value ?? "",
  );
  const [apiKey, setApiKey] = useState("");
  const [mcpUrl, setMcpUrl] = useState("");
  const [mcpAuth, setMcpAuth] = useState("");
  const [openapiUrl, setOpenapiUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSave = async () => {
    setLoading(true);
    setError(null);
    const entry: ProviderEntry =
      mode === "builtin"
        ? { mode: "builtin", provider: builtinProvider, api_key: apiKey }
        : mode === "mcp"
          ? { mode: "mcp", mcp_url: mcpUrl, mcp_auth_header: mcpAuth || undefined }
          : { mode: "openapi", openapi_spec_url: openapiUrl, api_key: apiKey };
    try {
      const result = await addProvider({ category, entry });
      if (!result.ok) {
        onSaved(result.error || "Provider test failed. Check your API key and try again.");
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
        Add {category} provider
      </h3>
      <div className="flex p-1 bg-[--color-surface-hover] rounded-[--radius-md] w-fit mb-5">
        {(["builtin", "mcp", "openapi"] as Mode[]).map((m) => {
          const disabled = m === "mcp" && !allowMcp;
          return (
            <button
              key={m}
              type="button"
              disabled={disabled}
              onClick={() => !disabled && setMode(m)}
              className={`px-3 py-1.5 rounded-[--radius-sm] text-sm capitalize ${
                mode === m ? "bg-[--color-bg-elevated] shadow-sm font-medium" : ""
              } ${disabled ? "opacity-40 cursor-not-allowed" : ""}`}
            >
              {m === "mcp" ? "MCP URL" : m === "openapi" ? "OpenAPI" : "Built-in"}
            </button>
          );
        })}
      </div>

      {mode === "builtin" ? (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">Provider</span>
            <select
              value={builtinProvider}
              onChange={(e) => setBuiltinProvider(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            >
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
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
        </>
      ) : mode === "mcp" ? (
        <>
          <MCPInfoCard />
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">MCP URL</span>
            <input
              value={mcpUrl}
              onChange={(e) => setMcpUrl(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <details className="mb-5">
            <summary className="text-sm text-[--color-text-secondary] cursor-pointer">Advanced</summary>
            <label className="flex flex-col gap-1.5 mt-3">
              <span className="text-sm font-medium text-[--color-text-primary]">Auth header</span>
              <input
                value={mcpAuth}
                onChange={(e) => setMcpAuth(e.target.value)}
                placeholder="Bearer sk_…"
                className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
              />
            </label>
          </details>
        </>
      ) : (
        <>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">OpenAPI spec URL</span>
            <input
              value={openapiUrl}
              onChange={(e) => setOpenapiUrl(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
            />
          </label>
          <label className="flex flex-col gap-1.5 mb-5">
            <span className="text-sm font-medium text-[--color-text-primary]">API key</span>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              className="h-10 px-3 rounded-[--radius-md] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
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
