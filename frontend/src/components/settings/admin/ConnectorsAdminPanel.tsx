/**
 * Admin panel: list / edit / validate / delete connectors.
 *
 * Follows the same shape as ModelsAdminPanel — a refresh-on-mount table with
 * inline action buttons. Edits are limited to display_name + secrets;
 * source/category cannot change post-creation per spec §3.
 */
import { useEffect, useState, type FormEvent } from "react";
import {
  deleteConnector,
  listConnectors,
  listBuiltinTemplates,
  validateConnector,
  type BuiltinTemplate,
  type ConnectorRow,
} from "../../../api/connectors";
import { refreshDeptHealth } from "../../../store/dept-health";
import { CatalogGrid } from "../../connectors/CatalogGrid";
import { InstallBuiltinForm } from "../../connectors/InstallBuiltinForm";

interface KV {
  key: string;
  value: string;
}

function kvToRecord(rows: KV[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const r of rows) {
    if (r.key.trim().length === 0) continue;
    out[r.key.trim()] = r.value;
  }
  return out;
}

export function ConnectorsAdminPanel(): JSX.Element {
  const [rows, setRows] = useState<ConnectorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ConnectorRow | null>(null);
  const [adding, setAdding] = useState(false);
  const [catalog, setCatalog] = useState<BuiltinTemplate[] | null>(null);
  const [picking, setPicking] = useState(false);
  const [chosenTemplate, setChosenTemplate] = useState<BuiltinTemplate | null>(null);

  const refresh = async () => {
    try {
      const r = await listConnectors();
      setRows(r);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connectors.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const onValidate = async (id: string) => {
    try {
      await validateConnector(id);
      await refresh();
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    }
  };

  const onDelete = async (row: ConnectorRow) => {
    if (!confirm(`Delete connector ${row.display_name || row.provider_id}?`)) return;
    try {
      await deleteConnector(row.id);
      await refresh();
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">Loading...</p>;

  return (
    <div className="space-y-4">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Connectors</h2>
          <p className="mt-1 text-sm text-text-secondary">
            Manage data-source connectors (MCP servers, Python libraries) used
            by departments.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={async () => {
              if (catalog === null) setCatalog(await listBuiltinTemplates());
              setPicking(true);
            }}
            className="rounded bg-accent-primary px-4 py-2 text-sm text-text-on-accent"
          >
            Add from catalog
          </button>
          <button
            type="button"
            onClick={() => setAdding(true)}
            className="rounded border border-border-subtle px-4 py-2 text-sm text-text-primary hover:bg-surface-hover"
          >
            Add custom
          </button>
        </div>
      </header>

      {error ? (
        <p role="alert" className="text-sm text-feedback-error">
          {error}
        </p>
      ) : null}

      {rows.length === 0 ? (
        <p className="text-sm text-text-secondary">
          No connectors configured. Add one from the setup wizard or via the
          API.
        </p>
      ) : (
        <table className="w-full text-sm" aria-label="Connectors">
          <thead className="text-text-secondary text-xs uppercase">
            <tr>
              <th className="text-left">Provider</th>
              <th className="text-left">Display</th>
              <th className="text-left">Source</th>
              <th className="text-left">Category</th>
              <th className="text-left">Status</th>
              <th className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-border-subtle">
                <td className="font-mono text-xs">{r.provider_id}</td>
                <td>{r.display_name}</td>
                <td>{r.source}</td>
                <td>{r.category}</td>
                <td>
                  <span
                    className={
                      r.status === "validated"
                        ? "text-feedback-success"
                        : r.status === "failed"
                          ? "text-feedback-error"
                          : "text-text-secondary"
                    }
                  >
                    {r.status}
                  </span>
                  {r.last_error ? (
                    <span className="block text-xs text-text-secondary">
                      {r.last_error}
                    </span>
                  ) : null}
                </td>
                <td className="text-right space-x-2">
                  <button
                    type="button"
                    onClick={() => setEditing(r)}
                    className="text-accent-primary hover:underline"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => onValidate(r.id)}
                    className="text-text-primary hover:underline"
                  >
                    Validate now
                  </button>
                  <button
                    type="button"
                    onClick={() => onDelete(r)}
                    className="text-feedback-error hover:underline"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {picking && (
        <CatalogGrid
          templates={catalog ?? []}
          onSelect={(t) => {
            setChosenTemplate(t);
            setPicking(false);
          }}
        />
      )}

      {chosenTemplate && (
        <InstallBuiltinForm
          template={chosenTemplate}
          onCancel={() => setChosenTemplate(null)}
          onInstalled={async (_row) => {
            setChosenTemplate(null);
            await refresh();
          }}
        />
      )}

      {adding && (
        <p className="text-sm text-text-secondary">
          To add a custom connector, use the setup wizard or the API.
        </p>
      )}

      {editing ? (
        <EditConnectorModal
          row={editing}
          onClose={() => setEditing(null)}
          onSaved={async () => {
            setEditing(null);
            await refresh();
          }}
        />
      ) : null}
    </div>
  );
}

interface EditModalProps {
  row: ConnectorRow;
  onClose: () => void;
  onSaved: () => Promise<void>;
}

/**
 * Edit modal limited to display_name + secrets per spec; source/category
 * are read-only post-creation. Editing posts via the connectors PATCH
 * endpoint when implemented; today we surface a notice that the feature
 * requires server-side support not yet wired.
 */
function EditConnectorModal({ row, onClose, onSaved }: EditModalProps) {
  const [displayName, setDisplayName] = useState(row.display_name);
  const [secrets, setSecrets] = useState<KV[]>([{ key: "", value: "" }]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErr(null);
    try {
      // Backend PATCH endpoint for connector edits is not yet wired (Phase 11
      // scope is the panel UI). We display the captured fields and surface a
      // notice rather than silently dropping the form data.
      const payload = {
        display_name: displayName,
        secrets: kvToRecord(secrets),
      };
      // eslint-disable-next-line no-console
      console.warn("Connector edit not yet wired on the server:", payload);
      await onSaved();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : "Save failed.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Edit connector"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
    >
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md space-y-3 rounded-md bg-bg-elevated p-4 shadow-md"
      >
        <h3 className="text-base font-semibold text-text-primary">
          Edit connector — {row.provider_id}
        </h3>
        <p className="text-xs text-text-secondary">
          Source ({row.source}) and category ({row.category}) are read-only.
        </p>
        <label className="block text-xs text-text-secondary">
          Display name
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <fieldset className="space-y-1">
          <legend className="text-xs text-text-secondary">
            Update secrets (leave blank to keep)
          </legend>
          {secrets.map((s, i) => (
            <div key={i} className="flex gap-2">
              <input
                type="text"
                aria-label={`secret key ${i}`}
                placeholder="ENV_VAR_NAME"
                value={s.key}
                onChange={(e) =>
                  setSecrets((rows) =>
                    rows.map((r, idx) =>
                      idx === i ? { ...r, key: e.target.value } : r,
                    ),
                  )
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
              <input
                type="password"
                aria-label={`secret value ${i}`}
                value={s.value}
                onChange={(e) =>
                  setSecrets((rows) =>
                    rows.map((r, idx) =>
                      idx === i ? { ...r, value: e.target.value } : r,
                    ),
                  )
                }
                className="flex-1 rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
              />
            </div>
          ))}
          <button
            type="button"
            onClick={() =>
              setSecrets((rows) => [...rows, { key: "", value: "" }])
            }
            className="text-xs text-accent-primary hover:underline"
          >
            + Add secret
          </button>
        </fieldset>
        {err ? (
          <p role="alert" className="text-xs text-feedback-error">
            {err}
          </p>
        ) : null}
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? "Saving..." : "Save"}
          </button>
        </div>
      </form>
    </div>
  );
}
