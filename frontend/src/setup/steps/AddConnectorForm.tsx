import { useState, type FormEvent } from "react";
import {
  createConnector,
  type Category,
  type ConnectorRow,
  type ConnectorSource,
  type CreateConnectorInput,
  type ModeIn,
} from "../../api/connectors";
import { parseMcpConfig } from "./parseMcpConfig";

type Source = "cli_mcp" | "remote_mcp" | "python_lib";

const SOURCES: { value: Source; label: string }[] = [
  { value: "cli_mcp", label: "CLI MCP" },
  { value: "remote_mcp", label: "Remote MCP" },
  { value: "python_lib", label: "Python library" },
];

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "financial", label: "Financial" },
  { value: "news", label: "News" },
  { value: "social", label: "Social" },
  { value: "web_search", label: "Web search" },
];

interface KV {
  key: string;
  value: string;
}

function parseArgv(s: string): string[] {
  return s
    .trim()
    .split(/\s+/)
    .filter((x) => x.length > 0);
}

function parseCSV(s: string): string[] {
  return s
    .split(",")
    .map((x) => x.trim())
    .filter((x) => x.length > 0);
}

function kvToRecord(rows: KV[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const r of rows) {
    if (r.key.trim().length === 0) continue;
    out[r.key.trim()] = r.value;
  }
  return out;
}

interface Props {
  onCancel: () => void;
  onCreated: (row: ConnectorRow) => void;
}

export function AddConnectorForm({ onCancel, onCreated }: Props) {
  const [source, setSource] = useState<Source>("cli_mcp");
  const [providerId, setProviderId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [category, setCategory] = useState<Category>("financial");

  // cli_mcp
  const [argvText, setArgvText] = useState("");
  const [envKeysText, setEnvKeysText] = useState("");
  const [mcpJsonText, setMcpJsonText] = useState("");
  const [mcpJsonError, setMcpJsonError] = useState<string | null>(null);

  // remote_mcp
  const [url, setUrl] = useState("");
  const [headers, setHeaders] = useState<KV[]>([{ key: "", value: "" }]);

  // python_lib
  const [pipName, setPipName] = useState("");
  const [pipVersion, setPipVersion] = useState("");
  const [importModule, setImportModule] = useState("");
  const [factoryCls, setFactoryCls] = useState("");
  const [factoryArgs, setFactoryArgs] = useState("{}");

  // secrets / API keys
  const [secrets, setSecrets] = useState<KV[]>([{ key: "", value: "" }]);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateKV =
    (setter: (rows: KV[]) => void, rows: KV[]) =>
    (idx: number, patch: Partial<KV>) => {
      const next = rows.map((r, i) => (i === idx ? { ...r, ...patch } : r));
      setter(next);
    };
  const addKV =
    (setter: (rows: KV[]) => void, rows: KV[]) =>
    () => setter([...rows, { key: "", value: "" }]);

  const onMcpJsonChange = (text: string) => {
    setMcpJsonText(text);
    if (text.trim().length === 0) {
      setMcpJsonError(null);
      return;
    }
    const result = parseMcpConfig(text);
    if (!result.ok) {
      setMcpJsonError(result.error);
      return;
    }
    setMcpJsonError(null);
    setProviderId(result.providerId);
    setArgvText(result.argv.join(" "));
    setEnvKeysText(result.envKeys.join(", "));
    setSecrets(
      result.secrets.length > 0 ? result.secrets : [{ key: "", value: "" }],
    );
  };

  const buildMode = (): ModeIn => {
    if (source === "cli_mcp") {
      return {
        kind: "cli_mcp",
        argv: parseArgv(argvText),
        env_keys: parseCSV(envKeysText),
      };
    }
    if (source === "remote_mcp") {
      return {
        kind: "remote_mcp",
        url: url.trim(),
        headers: kvToRecord(headers),
      };
    }
    // python_lib
    let parsedFactoryArgs: Record<string, unknown> = {};
    if (factoryArgs.trim().length > 0) {
      parsedFactoryArgs = JSON.parse(factoryArgs);
    }
    return {
      kind: "python_lib",
      pip_name: pipName.trim(),
      pip_version: pipVersion.trim() || undefined,
      import_module: importModule.trim(),
      instance_factory: {
        cls: factoryCls.trim(),
        args: parsedFactoryArgs,
      },
    };
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const mode = buildMode();
      const payload: CreateConnectorInput = {
        provider_id: providerId.trim(),
        display_name: displayName.trim() || providerId.trim(),
        source: source as ConnectorSource,
        category,
        launch: { modes: [mode] },
        secrets: kvToRecord(secrets),
      };
      const row = await createConnector(payload);
      onCreated(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create connector.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      aria-label="Add connector"
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-text-secondary">
          Source
          <select
            aria-label="source"
            value={source}
            onChange={(e) => setSource(e.target.value as Source)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          >
            {SOURCES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-text-secondary">
          Category
          <select
            aria-label="category"
            value={category}
            onChange={(e) => setCategory(e.target.value as Category)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          >
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
        <label className="text-xs text-text-secondary">
          Provider id
          <input
            type="text"
            required
            value={providerId}
            onChange={(e) => setProviderId(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <label className="text-xs text-text-secondary">
          Display name
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
      </div>

      {source === "cli_mcp" ? (
        <div className="space-y-2">
          <label className="block text-xs text-text-secondary">
            Paste MCP config (JSON)
            <textarea
              aria-label="paste mcp config"
              rows={4}
              placeholder='{ "mcpServers": { "newsapi": { "command": "npx", "args": ["-y", "newsapi-mcp"], "env": { "NEWSAPI_KEY": "..." } } } }'
              value={mcpJsonText}
              onChange={(e) => onMcpJsonChange(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
            />
          </label>
          {mcpJsonError ? (
            <p role="alert" className="text-xs text-feedback-error">
              {mcpJsonError}
            </p>
          ) : null}
          <label className="block text-xs text-text-secondary">
            argv (space-separated)
            <input
              type="text"
              required
              placeholder="npx -y my-mcp-server"
              value={argvText}
              onChange={(e) => setArgvText(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <label className="block text-xs text-text-secondary">
            env keys (comma-separated)
            <input
              type="text"
              placeholder="POLYGON_API_KEY, OTHER_VAR"
              value={envKeysText}
              onChange={(e) => setEnvKeysText(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
        </div>
      ) : null}

      {source === "remote_mcp" ? (
        <div className="space-y-2">
          <label className="block text-xs text-text-secondary">
            URL
            <input
              type="url"
              required
              placeholder="https://mcp.example.com/sse"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <fieldset className="space-y-1">
            <legend className="text-xs text-text-secondary">Headers</legend>
            {headers.map((h, i) => (
              <div key={i} className="flex gap-2">
                <input
                  type="text"
                  aria-label={`header key ${i}`}
                  placeholder="key"
                  value={h.key}
                  onChange={(e) =>
                    updateKV(setHeaders, headers)(i, { key: e.target.value })
                  }
                  className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
                <input
                  type="text"
                  aria-label={`header value ${i}`}
                  placeholder="value"
                  value={h.value}
                  onChange={(e) =>
                    updateKV(setHeaders, headers)(i, { value: e.target.value })
                  }
                  className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </div>
            ))}
            <button
              type="button"
              onClick={addKV(setHeaders, headers)}
              className="text-xs text-accent-primary hover:underline"
            >
              + Add header
            </button>
          </fieldset>
        </div>
      ) : null}

      {source === "python_lib" ? (
        <div className="space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-text-secondary">
              pip name
              <input
                type="text"
                required
                value={pipName}
                onChange={(e) => setPipName(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </label>
            <label className="text-xs text-text-secondary">
              pip version (optional)
              <input
                type="text"
                value={pipVersion}
                onChange={(e) => setPipVersion(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </label>
            <label className="text-xs text-text-secondary">
              import module
              <input
                type="text"
                required
                placeholder="eodhd"
                value={importModule}
                onChange={(e) => setImportModule(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </label>
            <label className="text-xs text-text-secondary">
              instance factory class
              <input
                type="text"
                placeholder="APIClient"
                value={factoryCls}
                onChange={(e) => setFactoryCls(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </label>
          </div>
          <label className="block text-xs text-text-secondary">
            instance factory args (JSON)
            <textarea
              rows={3}
              value={factoryArgs}
              onChange={(e) => setFactoryArgs(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
            />
          </label>
        </div>
      ) : null}

      <fieldset className="space-y-1">
        <legend className="text-xs text-text-secondary">API keys / secrets</legend>
        {secrets.map((s, i) => (
          <div key={i} className="flex gap-2">
            <input
              type="text"
              aria-label={`secret key ${i}`}
              placeholder="ENV_VAR_NAME"
              value={s.key}
              onChange={(e) =>
                updateKV(setSecrets, secrets)(i, { key: e.target.value })
              }
              className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
            <input
              type="password"
              aria-label={`secret value ${i}`}
              placeholder="value"
              value={s.value}
              onChange={(e) =>
                updateKV(setSecrets, secrets)(i, { value: e.target.value })
              }
              className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </div>
        ))}
        <button
          type="button"
          onClick={addKV(setSecrets, secrets)}
          className="text-xs text-accent-primary hover:underline"
        >
          + Add secret
        </button>
      </fieldset>

      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Saving..." : "Create connector"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
