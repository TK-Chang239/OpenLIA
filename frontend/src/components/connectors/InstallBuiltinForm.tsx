import { useState } from "react";
import {
  installBuiltin,
  type BuiltinTemplate,
  type ConnectorRow,
} from "../../api/connectors";

interface Props {
  template: BuiltinTemplate;
  onCancel: () => void;
  onInstalled: (row: ConnectorRow) => void;
}

export function InstallBuiltinForm({ template, onCancel, onInstalled }: Props) {
  const [apiKey, setApiKey] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const row = await installBuiltin({
        template_id: template.template_id,
        api_key: apiKey,
      });
      onInstalled(row);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Install failed.");
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
      <div className="flex items-center gap-2">
        <button
          type="submit"
          disabled={submitting || !apiKey}
          className="rounded-md bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {submitting ? "Installing..." : "Install"}
        </button>
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
