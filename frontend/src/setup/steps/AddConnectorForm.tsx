import { useState, type FormEvent } from "react";
import {
  createConnector,
  installPythonPackage,
  introspectPythonLib,
  updateConnector,
  type Category,
  type ConnectorRow,
  type ConnectorSource,
  type CreateConnectorInput,
  type LaunchIn,
  type ModeIn,
} from "../../api/connectors";
import { ApiError } from "../../api/client";
import { parseMcpConfig } from "./parseMcpConfig";
import { parseNpxCommand } from "./parseNpxCommand";
import { parsePipCommand } from "./parsePipCommand";

type Source = "cli_mcp" | "remote_mcp" | "python_lib";

export interface EditingConnector {
  id: string;
  providerId: string;
  displayName: string;
  source: ConnectorSource;
  category: Category;
  launch: LaunchIn;
  secretKeys: string[];
  sourceRepoUrl?: string | null;
  sourceRepoRevision?: string | null;
  groundingPaths?: string[] | null;
  openapiUrl?: string | null;
}

const SOURCES: { value: Source; label: string }[] = [
  { value: "cli_mcp", label: "Local MCP server (CLI / npx)" },
  { value: "remote_mcp", label: "Remote MCP server (URL)" },
  { value: "python_lib", label: "Python library (pip)" },
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
  editing?: EditingConnector;
}

function findMode(launch: LaunchIn | undefined, kind: string): ModeIn | undefined {
  return launch?.modes.find((m) => m.kind === kind);
}

export function AddConnectorForm({ onCancel, onCreated, editing }: Props) {
  const isEditing = editing !== undefined;
  const initialSource: Source = (editing?.source as Source) ?? "cli_mcp";
  const cliMode = findMode(editing?.launch, "cli_mcp");
  const remoteMode = findMode(editing?.launch, "remote_mcp");
  const pyMode = findMode(editing?.launch, "python_lib");

  const [source, setSource] = useState<Source>(initialSource);
  const [providerId, setProviderId] = useState(editing?.providerId ?? "");
  const [displayName, setDisplayName] = useState(editing?.displayName ?? "");
  const [category, setCategory] = useState<Category>(
    editing?.category ?? "financial",
  );

  // cli_mcp
  const [argvText, setArgvText] = useState(
    cliMode?.argv ? cliMode.argv.join(" ") : "",
  );
  const [envKeysText, setEnvKeysText] = useState(
    cliMode?.env_keys ? cliMode.env_keys.join(", ") : "",
  );
  const [mcpJsonText, setMcpJsonText] = useState("");
  const [mcpJsonError, setMcpJsonError] = useState<string | null>(null);

  // remote_mcp
  const [url, setUrl] = useState(remoteMode?.url ?? "");
  const [headers, setHeaders] = useState<KV[]>(() => {
    const h = remoteMode?.headers;
    if (!h || Object.keys(h).length === 0) return [{ key: "", value: "" }];
    return Object.entries(h).map(([key, value]) => ({ key, value }));
  });

  // python_lib
  const [pipName, setPipName] = useState(pyMode?.pip_name ?? "");
  const [pipVersion, setPipVersion] = useState(pyMode?.pip_version ?? "");
  const [importModule, setImportModule] = useState(pyMode?.import_module ?? "");
  const initialFactory = (pyMode?.instance_factory ?? {}) as {
    cls?: string;
    args?: Record<string, unknown>;
  };
  const [factoryCls, setFactoryCls] = useState(initialFactory.cls ?? "");
  const [factoryArgs, setFactoryArgs] = useState(
    initialFactory.args ? JSON.stringify(initialFactory.args, null, 2) : "{}",
  );
  const [pipCmdText, setPipCmdText] = useState("");
  const [pipCmdError, setPipCmdError] = useState<string | null>(null);
  const [detectError, setDetectError] = useState<string | null>(null);
  const [detectStatus, setDetectStatus] = useState<string | null>(null);
  const [detecting, setDetecting] = useState(false);
  const [installing, setInstalling] = useState(false);
  const [installStatus, setInstallStatus] = useState<string | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);

  // secrets / API keys
  const [secrets, setSecrets] = useState<KV[]>(() => {
    const keys = editing?.secretKeys ?? [];
    if (keys.length === 0) return [{ key: "", value: "" }];
    return keys.map((k) => ({ key: k, value: "" }));
  });

  // grounding URLs (improve adapter accuracy)
  const [sourceRepoUrl, setSourceRepoUrl] = useState<string>(
    editing?.sourceRepoUrl ?? "",
  );
  const [sourceRepoRevision, setSourceRepoRevision] = useState<string>(
    editing?.sourceRepoRevision ?? "",
  );
  const [openapiUrl, setOpenapiUrl] = useState<string>(
    editing?.openapiUrl ?? "",
  );
  const [groundingPathsRaw, setGroundingPathsRaw] = useState<string>(
    (editing?.groundingPaths ?? []).join("\n"),
  );

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
    if (text.trimStart().startsWith("npx")) {
      const npx = parseNpxCommand(text);
      if (!npx.ok) {
        setMcpJsonError(npx.error);
        return;
      }
      setMcpJsonError(null);
      setProviderId(npx.providerId);
      setArgvText(npx.argv.join(" "));
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

  const onInstallPackage = async () => {
    setInstallError(null);
    setInstallStatus(null);
    if (pipName.trim().length === 0) {
      setInstallError("Fill in 'pip name' first.");
      return;
    }
    setInstalling(true);
    try {
      const { stdout } = await installPythonPackage(
        pipName.trim(),
        pipVersion.trim(),
      );
      // Surface the most useful one-liner from pip's chatter.
      const successLine =
        stdout
          .split(/\r?\n/)
          .reverse()
          .find((l) => /successfully installed/i.test(l)) ?? stdout.trim();
      setInstallStatus(successLine || "Installed.");
    } catch (err) {
      let msg = "Install failed.";
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        msg = body?.detail ?? err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setInstallError(msg);
    } finally {
      setInstalling(false);
    }
  };

  const onDetectParameters = async () => {
    setDetectError(null);
    setDetectStatus(null);
    if (importModule.trim().length === 0 || factoryCls.trim().length === 0) {
      setDetectError(
        "Fill in 'import module' and 'main client class' first.",
      );
      return;
    }
    setDetecting(true);
    try {
      const { params } = await introspectPythonLib(
        importModule.trim(),
        factoryCls.trim(),
      );
      // Treat any param whose name looks like a credential as a secret,
      // regardless of whether `inspect.signature` marks it required. Many
      // SDKs default API-key params to None and then raise at call-time,
      // so a "not required" flag is misleading here.
      const SECRET_RE = /(api[_-]?key|token|secret|password|passphrase)/i;
      const args: Record<string, unknown> = {};
      const newSecrets: KV[] = [];
      for (const p of params) {
        const isSecret = SECRET_RE.test(p.name);
        if (isSecret) {
          const secretKey = p.name.toUpperCase();
          args[p.name] = `$${secretKey}`;
          newSecrets.push({ key: secretKey, value: "" });
        } else if (p.required) {
          args[p.name] = "";
        } else if (p.default !== null && p.default !== undefined) {
          args[p.name] = p.default;
        }
      }
      setFactoryArgs(JSON.stringify(args, null, 2));
      setDetectStatus(
        `Detected ${params.length} parameter${params.length === 1 ? "" : "s"} (${newSecrets.length} secret${newSecrets.length === 1 ? "" : "s"}).`,
      );
      // Merge detected secret keys into the existing list, preserving any
      // already-typed values for matching keys.
      setSecrets((prev) => {
        const byKey = new Map<string, string>();
        for (const row of prev) {
          if (row.key.trim().length > 0) byKey.set(row.key.trim(), row.value);
        }
        const merged: KV[] = newSecrets.map((s) => ({
          key: s.key,
          value: byKey.get(s.key) ?? "",
        }));
        // Keep extra existing keys the user added that we didn't auto-detect.
        for (const row of prev) {
          const k = row.key.trim();
          if (k.length > 0 && !merged.some((m) => m.key === k)) {
            merged.push(row);
          }
        }
        return merged.length > 0 ? merged : [{ key: "", value: "" }];
      });
    } catch (err) {
      let msg = "Could not detect parameters.";
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        msg = body?.detail ?? err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setDetectError(msg);
    } finally {
      setDetecting(false);
    }
  };

  const onPipCmdChange = (text: string) => {
    setPipCmdText(text);
    if (text.trim().length === 0) {
      setPipCmdError(null);
      return;
    }
    const result = parsePipCommand(text);
    if (!result.ok) {
      setPipCmdError(result.error);
      return;
    }
    setPipCmdError(null);
    setPipName(result.pipName);
    setPipVersion(result.pipVersion);
    setImportModule(result.importModule);
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
      // In edit mode, only send `secrets` if the user typed at least one value.
      // Empty values mean "keep the existing secret".
      const enteredSecrets = secrets.filter(
        (s) => s.key.trim().length > 0 && s.value.length > 0,
      );
      const includeSecrets = isEditing
        ? enteredSecrets.length > 0
        : true;
      const payload: CreateConnectorInput = {
        provider_id: providerId.trim(),
        display_name: displayName.trim() || providerId.trim(),
        source: source as ConnectorSource,
        category,
        launch: { modes: [mode] },
        ...(includeSecrets
          ? {
              secrets: kvToRecord(
                isEditing ? enteredSecrets : secrets,
              ),
            }
          : {}),
        source_repo_url: sourceRepoUrl.trim() || null,
        source_repo_revision: sourceRepoRevision.trim() || null,
        grounding_paths: (() => {
          const parts = groundingPathsRaw
            .split(/[\n,]/)
            .map((s) => s.trim())
            .filter((s) => s.length > 0);
          return parts.length > 0 ? parts : null;
        })(),
        openapi_url: openapiUrl.trim() || null,
      };
      const row = isEditing
        ? await updateConnector(editing!.id, payload)
        : await createConnector(payload);
      onCreated(row);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : isEditing
            ? "Failed to update connector."
            : "Failed to create connector.",
      );
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
        <div>
          <label className="block text-xs text-text-secondary">
            Provider id
            <input
              type="text"
              required
              value={providerId}
              onChange={(e) => setProviderId(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <p
            data-testid="hint-provider-id"
            className="mt-0.5 text-[10px] text-text-secondary"
          >
            Short identifier (lowercase, no spaces). Used in tool names and logs.
          </p>
        </div>
        <div>
          <label className="block text-xs text-text-secondary">
            Display name
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
            />
          </label>
          <p className="mt-0.5 text-[10px] text-text-secondary">
            Friendly name shown in the UI. Optional.
          </p>
        </div>
      </div>

      {source === "cli_mcp" ? (
        <div className="space-y-2">
          <div>
            <label className="block text-xs text-text-secondary">
              Paste MCP config (JSON) or `npx` command
              <textarea
                aria-label="paste mcp config"
                rows={4}
                placeholder='npx -y newsapi-mcp     —or—     { "mcpServers": { "newsapi": { "command": "npx", "args": ["-y", "newsapi-mcp"], "env": { "NEWSAPI_KEY": "..." } } } }'
                value={mcpJsonText}
                onChange={(e) => onMcpJsonChange(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
              />
            </label>
            <p className="mt-0.5 text-[10px] text-text-secondary">
              Paste what the provider's docs show — either a bare `npx ...` command or
              the full `mcpServers` JSON. Auto-fills the fields below.
            </p>
          </div>
          {mcpJsonError ? (
            <p role="alert" className="text-xs text-feedback-error">
              {mcpJsonError}
            </p>
          ) : null}
          <div>
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
            <p className="mt-0.5 text-[10px] text-text-secondary">
              Command that launches the MCP server, split by spaces. Usually starts
              with `npx -y …` or `uvx …`.
            </p>
          </div>
          <div>
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
            <p className="mt-0.5 text-[10px] text-text-secondary">
              Environment variables the server reads. Their values come from the
              secrets section below.
            </p>
          </div>
        </div>
      ) : null}

      {source === "remote_mcp" ? (
        <div className="space-y-2">
          <p
            data-testid="hint-remote-oauth"
            className="rounded-md border border-border-subtle bg-bg-subtle px-2 py-1 text-[10px] text-text-secondary"
          >
            OAuth is not supported yet. If your provider offers both an
            OAuth-authenticated endpoint and an API-key-in-URL endpoint, use
            the URL form (e.g. `https://mcp.example.com/mcp?api_token=YOUR_KEY`).
            For static bearer tokens, paste them as an `Authorization` header
            below.
          </p>
          <div>
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
            <p className="mt-0.5 text-[10px] text-text-secondary">
              The MCP server's HTTPS endpoint (often ends in `/sse` or `/mcp`).
              Include any required `?api_token=…` query parameter directly in
              the URL.
            </p>
          </div>
          <fieldset className="space-y-1">
            <legend className="text-xs text-text-secondary">Headers</legend>
            <p className="text-[10px] text-text-secondary">
              Auth headers required by the server. Typically `Authorization: Bearer
              &lt;static-token&gt;`. Leave empty if the API key is in the URL.
            </p>
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
          <div>
            <label className="block text-xs text-text-secondary">
              Paste pip install command (optional)
              <textarea
                rows={2}
                aria-label="paste pip install command"
                placeholder="python3 -m pip install eodhd -U"
                value={pipCmdText}
                onChange={(e) => onPipCmdChange(e.target.value)}
                className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
              />
            </label>
            <p className="mt-0.5 text-[10px] text-text-secondary">
              Paste the install command from the library's docs. Auto-fills the
              package fields below.
            </p>
          </div>
          {pipCmdError ? (
            <p role="alert" className="text-xs text-red-500">
              {pipCmdError}
            </p>
          ) : null}
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={onInstallPackage}
              disabled={installing}
              className="rounded-md border border-border-subtle px-2 py-1 text-xs text-text-primary hover:bg-surface-hover disabled:opacity-50"
            >
              {installing ? "Installing..." : "Install package"}
            </button>
            <p className="text-[10px] text-text-secondary">
              Runs `pip install` on the server using the values below. Required
              before "Detect parameters" works for new packages.
            </p>
          </div>
          {installStatus ? (
            <p
              data-testid="install-status"
              role="status"
              className="text-[10px] text-feedback-success"
            >
              {installStatus}
            </p>
          ) : null}
          {installError ? (
            <p
              data-testid="install-error"
              role="alert"
              className="text-[10px] text-feedback-error"
            >
              {installError}
            </p>
          ) : null}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs text-text-secondary">
                pip name
                <input
                  type="text"
                  required
                  value={pipName}
                  onChange={(e) => setPipName(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <p className="mt-0.5 text-[10px] text-text-secondary">
                PyPI package name — what you'd type after `pip install`.
              </p>
            </div>
            <div>
              <label className="block text-xs text-text-secondary">
                pip version (optional)
                <input
                  type="text"
                  value={pipVersion}
                  onChange={(e) => setPipVersion(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <p className="mt-0.5 text-[10px] text-text-secondary">
                Pin like `==1.2.3` or `&gt;=2.0`. Leave blank for latest.
              </p>
            </div>
            <div>
              <label className="block text-xs text-text-secondary">
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
              <p className="mt-0.5 text-[10px] text-text-secondary">
                What you write after `import` in Python. Often the same as the package name.
              </p>
            </div>
            <div>
              <label className="block text-xs text-text-secondary">
                Main client class (e.g. APIClient)
                <input
                  type="text"
                  placeholder="APIClient"
                  value={factoryCls}
                  onChange={(e) => setFactoryCls(e.target.value)}
                  className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
                />
              </label>
              <p className="mt-0.5 text-[10px] text-text-secondary">
                Class instantiated to access the API. Check the library's quickstart.
              </p>
            </div>
          </div>
          <div>
            <div className="flex items-center justify-between gap-2">
              <label className="block text-xs text-text-secondary">
                Constructor settings (JSON)
              </label>
              <button
                type="button"
                onClick={onDetectParameters}
                disabled={detecting}
                className="text-xs text-accent-primary hover:underline disabled:opacity-50"
              >
                {detecting ? "Detecting..." : "Detect parameters"}
              </button>
            </div>
            <textarea
              aria-label="constructor settings"
              rows={3}
              value={factoryArgs}
              onChange={(e) => setFactoryArgs(e.target.value)}
              className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
            />
            {detectError ? (
              <p
                data-testid="detect-error"
                role="alert"
                className="mt-0.5 text-[10px] text-feedback-error"
              >
                {detectError}
              </p>
            ) : null}
            {detectStatus ? (
              <p
                data-testid="detect-status"
                className="mt-0.5 text-[10px] text-feedback-success"
              >
                {detectStatus}
              </p>
            ) : null}
            <p
              data-testid="hint-factory-args"
              className="mt-0.5 text-[10px] text-text-secondary"
            >
              Keyword arguments passed to the class as JSON. Click "Detect
              parameters" to auto-fill from the library, or type manually using
              `"$VAR_NAME"` to reference a secret. Example: {"{"}"api_token": "$EODHD_API_KEY"{"}"}.
            </p>
          </div>
        </div>
      ) : null}

      <fieldset className="space-y-1">
        <legend className="text-xs text-text-secondary">API keys / secrets</legend>
        <p className="text-[10px] text-text-secondary">
          Stored encrypted on the server, never sent to the LLM. Key is the env
          var name; value is the actual secret.
        </p>
        {isEditing ? (
          <p className="text-[10px] text-text-secondary">
            Existing secret values are not shown. Leave a value blank to keep the
            saved secret unchanged; type a new value to overwrite it.
          </p>
        ) : null}
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

      <fieldset className="space-y-2 rounded-md border border-border-subtle p-2">
        <legend className="px-1 text-xs font-medium text-text-secondary">
          Improve adapter accuracy (optional)
        </legend>
        <p className="text-xs text-text-secondary">
          Provide a GitHub repo or OpenAPI URL so the adapter can read
          provider-specific enums and parameter taxonomies.
        </p>
        <label className="block text-xs text-text-secondary">
          GitHub repository URL
          <input
            type="url"
            value={sourceRepoUrl}
            onChange={(e) => setSourceRepoUrl(e.target.value)}
            placeholder="https://github.com/owner/repo"
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm"
          />
        </label>
        <label className="block text-xs text-text-secondary">
          Branch / tag / revision
          <input
            type="text"
            value={sourceRepoRevision}
            onChange={(e) => setSourceRepoRevision(e.target.value)}
            placeholder="main"
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm"
          />
        </label>
        <label className="block text-xs text-text-secondary">
          OpenAPI / Swagger URL
          <input
            type="url"
            value={openapiUrl}
            onChange={(e) => setOpenapiUrl(e.target.value)}
            placeholder="https://example.com/openapi.json"
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 text-sm"
          />
        </label>
        <label className="block text-xs text-text-secondary">
          Grounding paths (optional)
          <textarea
            value={groundingPathsRaw}
            onChange={(e) => setGroundingPathsRaw(e.target.value)}
            placeholder={"docs\nschemas\nREADME.md"}
            rows={3}
            className="mt-1 w-full rounded-md border border-border-subtle bg-bg-elevated px-2 py-1 font-mono text-xs"
          />
          <span className="mt-1 block text-[11px] text-text-tertiary">
            One path per line. Restricts the resolver's filesystem tools to
            these files / dirs inside the cloned repo. Leave empty to expose
            the whole clone.
          </span>
        </label>
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
          {submitting
            ? "Saving..."
            : isEditing
              ? "Save changes"
              : "Create connector"}
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
