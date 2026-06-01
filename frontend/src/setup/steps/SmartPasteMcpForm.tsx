import { useMemo, useState, type FormEvent } from "react";
import {
  createConnector,
  type Category,
  type ConnectorRow,
  type CreateConnectorInput,
} from "../../api/connectors";
import { ApiError } from "../../api/client";
import { parseMcpInput } from "./parseMcpInput";
import { detectSecrets, type SecretChip } from "./detectSecrets";
import { buildMcpLaunch } from "./buildMcpLaunch";

const CATEGORIES: { value: Category; label: string }[] = [
  { value: "financial", label: "Financial" },
  { value: "news", label: "News" },
  { value: "social", label: "Social" },
  { value: "web_search", label: "Web search" },
];

interface Props {
  onCancel: () => void;
  onCreated: (row: ConnectorRow) => void;
}

function deriveProviderId(text: string): string {
  const parsed = parseMcpInput(text);
  if (parsed.kind === "remote") {
    try {
      return new URL(parsed.baseUrl).hostname.split(".").slice(-2, -1)[0] ?? "";
    } catch {
      return "";
    }
  }
  if (parsed.kind === "cli" && parsed.serverIndex >= 0) {
    const tok = parsed.argv[parsed.serverIndex] ?? "";
    const base = tok.includes("/") ? tok.slice(tok.lastIndexOf("/") + 1) : tok;
    return base.replace(/-mcp$|^server-/g, "");
  }
  return "";
}

export function SmartPasteMcpForm({ onCancel, onCreated }: Props) {
  const [text, setText] = useState("");
  const [providerId, setProviderId] = useState("");
  const [providerEdited, setProviderEdited] = useState(false);
  const [displayName, setDisplayName] = useState("");
  const [displayEdited, setDisplayEdited] = useState(false);
  const [category, setCategory] = useState<Category>("financial");
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const parsed = useMemo(() => parseMcpInput(text), [text]);
  const effectiveProvider = providerEdited
    ? providerId
    : deriveProviderId(text);
  const effectiveDisplay = displayEdited ? displayName : effectiveProvider;

  const chips: SecretChip[] = useMemo(() => {
    if (parsed.kind === "error") return [];
    return detectSecrets(parsed, effectiveProvider || "connector");
  }, [parsed, effectiveProvider]);

  // Initialize enable/value state for newly-seen chips (pre-selected + raw value).
  const chipState = useMemo(() => {
    const en: Record<string, boolean> = {};
    const va: Record<string, string> = {};
    for (const c of chips) {
      en[c.suggestedKey] = enabled[c.suggestedKey] ?? c.preselected;
      const isPlaceholder = /^(your[_-]|<|\{)/i.test(c.rawValue);
      va[c.suggestedKey] =
        values[c.suggestedKey] ?? (isPlaceholder ? "" : c.rawValue);
    }
    return { en, va };
  }, [chips, enabled, values]);

  const hasEmptyEnabledSecret = chips.some(
    (c) => chipState.en[c.suggestedKey] && chipState.va[c.suggestedKey].trim() === "",
  );

  const canSubmit =
    parsed.kind !== "error" &&
    text.trim().length > 0 &&
    !submitting &&
    !hasEmptyEnabledSecret;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (parsed.kind === "error") return;
    setError(null);
    setSubmitting(true);
    try {
      const selected = chips.filter((c) => chipState.en[c.suggestedKey]);
      const built = buildMcpLaunch({
        parsed,
        selected,
        values: chipState.va,
      });
      const payload: CreateConnectorInput = {
        provider_id: (effectiveProvider || "connector").trim(),
        display_name: (effectiveDisplay || effectiveProvider || "connector").trim(),
        source: parsed.kind === "remote" ? "remote_mcp" : "cli_mcp",
        category,
        launch: { modes: [built.mode] },
        secrets: built.secrets,
      };
      const row = await createConnector(payload);
      onCreated(row);
    } catch (err) {
      let msg = "Failed to add connector.";
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string } | null;
        msg = body?.detail ?? err.message;
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      aria-label="Add MCP connector"
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <label className="block text-xs text-text-secondary">
        Paste a URL or command
        <textarea
          aria-label="paste a url or command"
          rows={3}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setEnabled({});
            setValues({});
            setDisplayName("");
            setDisplayEdited(false);
          }}
          placeholder="https://mcp.example.com/mcp?apikey=YOUR_KEY   —or—   uvx some-mcp-server YOUR_KEY"
          className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-xs text-text-primary"
        />
      </label>

      {parsed.kind === "error" && text.trim().length > 0 ? (
        <p role="alert" className="text-xs text-feedback-error">
          {parsed.error}
        </p>
      ) : null}

      {parsed.kind !== "error" && text.trim().length > 0 ? (
        <p data-testid="detected-kind" className="text-[10px] text-text-secondary">
          Detected: {parsed.kind === "remote" ? "Remote MCP server" : "Local MCP server"}
        </p>
      ) : null}

      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs text-text-secondary">
          Provider id
          <input
            type="text"
            aria-label="provider id"
            value={effectiveProvider}
            onChange={(e) => {
              setProviderEdited(true);
              setProviderId(e.target.value);
            }}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <label className="text-xs text-text-secondary">
          Display name
          <input
            type="text"
            aria-label="display name"
            value={effectiveDisplay}
            onChange={(e) => {
              setDisplayEdited(true);
              setDisplayName(e.target.value);
            }}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
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
      </div>

      {chips.length > 0 ? (
        <fieldset className="space-y-1">
          <legend className="text-xs text-text-secondary">Detected secrets</legend>
          <p className="text-[10px] text-text-secondary">
            Stored encrypted on the server, never sent to the LLM. Toggle off
            anything that is not a secret.
          </p>
          {chips.map((c) => (
            <div key={c.suggestedKey} className="flex items-center gap-2">
              <input
                type="checkbox"
                aria-label={`treat ${c.label} as secret`}
                checked={chipState.en[c.suggestedKey]}
                onChange={(e) =>
                  setEnabled((prev) => ({
                    ...prev,
                    [c.suggestedKey]: e.target.checked,
                  }))
                }
              />
              <span className="w-20 shrink-0 text-[10px] text-text-secondary">
                {c.label}
              </span>
              <input
                type="password"
                aria-label={`secret value ${c.label}`}
                value={chipState.va[c.suggestedKey]}
                onChange={(e) =>
                  setValues((prev) => ({
                    ...prev,
                    [c.suggestedKey]: e.target.value,
                  }))
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </div>
          ))}
        </fieldset>
      ) : null}

      {error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {error}
        </p>
      ) : null}

      <div className="space-y-1">
        {hasEmptyEnabledSecret ? (
          <p
            data-testid="empty-secret-hint"
            className="text-[10px] text-text-secondary"
          >
            Enter a value for each enabled secret, or toggle it off.
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          <button
            type="submit"
            disabled={!canSubmit}
            className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Validating..." : "Validate & add"}
          </button>
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
          >
            Cancel
          </button>
        </div>
      </div>
    </form>
  );
}
