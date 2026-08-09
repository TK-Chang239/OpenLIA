import { useState } from "react";
import {
  installBuiltin,
  deleteConnector,
  type BuiltinTemplate,
  type ConnectorRow,
} from "../../api/connectors";
import { ApiError } from "../../api/client";

interface Props {
  template: BuiltinTemplate;
  onCancel: () => void;
  onInstalled: (row: ConnectorRow) => void;
}

/**
 * install-builtin returns 409 when a connector for this provider already
 * exists; the body carries the existing connector's id so we can offer to
 * replace it instead of surfacing a raw "HTTP 409" error. Returns the
 * existing id, or null when the error is anything else.
 */
function existingIdFromConflict(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 409) return null;
  const body = err.body;
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail?: unknown }).detail;
    if (detail && typeof detail === "object" && "existing_id" in detail) {
      const id = (detail as { existing_id?: unknown }).existing_id;
      if (typeof id === "string") return id;
    }
  }
  return null;
}

export function InstallBuiltinForm({ template, onCancel, onInstalled }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [duplicateId, setDuplicateId] = useState<string | null>(null);

  const install = async () => {
    const row = await installBuiltin({
      template_id: template.template_id,
      api_key: apiKey,
    });
    onInstalled(row);
  };

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    setDuplicateId(null);
    try {
      await install();
    } catch (err) {
      const existingId = existingIdFromConflict(err);
      if (existingId) {
        setDuplicateId(existingId);
      } else {
        setError(err instanceof Error ? err.message : "Install failed.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onReplace = async () => {
    if (!duplicateId) return;
    setSubmitting(true);
    setError(null);
    try {
      await deleteConnector(duplicateId);
      setDuplicateId(null);
      await install();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Replace failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={onSubmit}
      className="space-y-3 rounded-md border border-border-subtle bg-bg-elevated p-3"
    >
      <h3 className="text-lg font-semibold text-text-primary">
        {template.display_name}
      </h3>
      <label className="block text-sm font-medium text-text-primary">
        API key
        <span className="ml-2 font-mono text-xs text-text-secondary">
          {template.api_key_env_var}
        </span>
        <input
          aria-label="API key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          required
          className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-feedback-error">
          {error}
        </p>
      )}
      {duplicateId && (
        <p role="alert" className="text-sm text-text-secondary">
          {template.display_name} is already installed. Replace it with this API
          key to update the stored credentials and re-validate.
        </p>
      )}
      <div className="flex items-center gap-2">
        {duplicateId ? (
          <button
            type="button"
            onClick={onReplace}
            disabled={submitting || !apiKey}
            className="rounded-md bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Replacing..." : "Replace existing"}
          </button>
        ) : (
          <button
            type="submit"
            disabled={submitting || !apiKey}
            className="rounded-md bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Installing..." : "Install"}
          </button>
        )}
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-border-subtle px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
