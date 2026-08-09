/**
 * Top-level Connectors settings section: list / edit / validate / delete
 * connectors. Visible to all users (no admin gating).
 *
 * The smart-paste form is the always-visible primary add path; "add from
 * catalog" and "advanced" are secondary links. A refresh-on-mount table with
 * inline action buttons. Edits are limited to display_name + secrets;
 * source/category cannot change post-creation per spec §3.
 */
import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import {
  deleteConnector,
  getConnector,
  listConnectors,
  listBuiltinTemplates,
  syncTemplateSpecs,
  updateConnector,
  validateConnector,
  type BuiltinTemplate,
  type ConnectorDetail,
  type ConnectorRow,
  type CreateConnectorInput,
} from "../../../api/connectors";
import { refreshDeptHealth, useDeptHealth } from "../../../store/dept-health";
import { CatalogGrid } from "../../connectors/CatalogGrid";
import { CategoryRequirementsPanel } from "../../connectors/CategoryRequirementsPanel";
import { InstallBuiltinForm } from "../../connectors/InstallBuiltinForm";
import { AddConnectorForm } from "../../../setup/steps/AddConnectorForm";
import { SmartPasteMcpForm } from "../../../setup/steps/SmartPasteMcpForm";

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

export function ConnectorsSection(): JSX.Element {
  const { t } = useTranslation();
  const [rows, setRows] = useState<ConnectorRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<ConnectorRow | null>(null);
  const [adding, setAdding] = useState(false);
  const [formNonce, setFormNonce] = useState(0);
  const [catalog, setCatalog] = useState<BuiltinTemplate[] | null>(null);
  const [picking, setPicking] = useState(false);
  const [chosenTemplate, setChosenTemplate] = useState<BuiltinTemplate | null>(null);

  const healths = useDeptHealth((s) => s.healths);

  const refresh = async () => {
    try {
      const r = await listConnectors();
      setRows(r);
      await refreshDeptHealth();
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.connectors.load_failed'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onValidate = async (id: string) => {
    try {
      await validateConnector(id);
      await refresh();
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.connectors.validate_failed'));
    }
  };

  const onDelete = async (row: ConnectorRow) => {
    if (!confirm(t('settings.connectors.confirm_delete', { name: row.display_name || row.provider_id }))) return;
    try {
      await deleteConnector(row.id);
      await refresh();
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.connectors.delete_failed'));
    }
  };

  const onSyncSpecs = async (row: ConnectorRow) => {
    try {
      const { inserted } = await syncTemplateSpecs(row.id);
      await refresh();
      await refreshDeptHealth();
      setError(null);
      alert(t('settings.connectors.sync_done', { count: inserted }));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('settings.connectors.sync_failed'));
    }
  };

  if (loading) return <p className="text-sm text-text-secondary">{t('settings.connectors.loading')}</p>;

  return (
    <div className="space-y-4">
      <header>
        <h2 className="text-base font-semibold text-text-primary">{t('settings.connectors.title')}</h2>
        <p className="mt-1 text-sm text-text-secondary">
          {t('settings.connectors.subtitle')}
        </p>
      </header>

      <SmartPasteMcpForm
        key={formNonce}
        onCreated={() => {
          setFormNonce((n) => n + 1);
          void refresh();
        }}
      />

      <div className="flex items-center gap-3 text-sm">
        <span className="text-text-secondary">{t('settings.connectors.other_ways')}</span>
        <button
          type="button"
          onClick={async () => {
            if (catalog === null) setCatalog(await listBuiltinTemplates());
            setPicking(true);
          }}
          className="text-accent-primary hover:underline"
        >
          {t('settings.connectors.add_from_catalog')}
        </button>
        <span className="text-text-secondary">·</span>
        <button
          type="button"
          onClick={() => setAdding(true)}
          className="text-accent-primary hover:underline"
        >
          {t('settings.connectors.add_advanced')}
        </button>
      </div>

      {error ? (
        <p role="alert" className="text-sm text-feedback-error">
          {error}
        </p>
      ) : null}

      <CategoryRequirementsPanel connectors={rows} healths={healths} />

      {rows.length === 0 ? (
        <p className="text-sm text-text-secondary">
          {t('settings.connectors.none_configured')}
        </p>
      ) : (
        <table className="w-full text-sm" aria-label={t('settings.connectors.table_aria')}>
          <thead className="text-text-secondary text-xs uppercase">
            <tr>
              <th className="text-left">{t('settings.connectors.col_provider')}</th>
              <th className="text-left">{t('settings.connectors.col_display')}</th>
              <th className="text-left">{t('settings.connectors.col_source')}</th>
              <th className="text-left">{t('settings.connectors.col_category')}</th>
              <th className="text-left">{t('settings.connectors.col_status')}</th>
              <th className="text-right">{t('settings.connectors.col_actions')}</th>
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
                    {t('settings.connectors.edit')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onValidate(r.id)}
                    className="text-text-primary hover:underline"
                  >
                    {t('settings.connectors.validate_now')}
                  </button>
                  {r.source === "built_in" ? (
                    <button
                      type="button"
                      onClick={() => onSyncSpecs(r)}
                      title={t('settings.connectors.sync_specs_title')}
                      className="text-text-primary hover:underline"
                    >
                      {t('settings.connectors.sync_specs')}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => onDelete(r)}
                    className="text-feedback-error hover:underline"
                  >
                    {t('settings.connectors.delete')}
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
        <AddConnectorForm
          onCancel={() => setAdding(false)}
          onCreated={(_row) => {
            setAdding(false);
            void refresh();
          }}
        />
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
 * are read-only post-creation. Saving PUTs the full connector (fetched via
 * the detail endpoint so launch config survives) with the edited display
 * name; secrets are only included when the user enters new ones, otherwise
 * the server preserves the existing secrets. The server re-validates on save.
 */
function EditConnectorModal({ row, onClose, onSaved }: EditModalProps) {
  const { t } = useTranslation();
  const [detail, setDetail] = useState<ConnectorDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(true);
  const [displayName, setDisplayName] = useState(row.display_name);
  const [secrets, setSecrets] = useState<KV[]>([{ key: "", value: "" }]);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const d = await getConnector(row.id);
        if (!cancelled) setDetail(d);
      } catch (e) {
        if (!cancelled)
          setErr(e instanceof Error ? e.message : t('settings.connectors.load_failed'));
      } finally {
        if (!cancelled) setLoadingDetail(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [row.id, t]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!detail) return;
    setSubmitting(true);
    setErr(null);
    try {
      const input: CreateConnectorInput = {
        provider_id: detail.provider_id,
        display_name: displayName,
        source: detail.source,
        category: detail.category,
        launch: detail.launch,
        source_repo_url: detail.source_repo_url ?? null,
        source_repo_revision: detail.source_repo_revision ?? null,
        grounding_paths: detail.grounding_paths ?? null,
        openapi_url: detail.openapi_url ?? null,
      };
      // Only send secrets the user actually entered; omitting the field tells
      // the server to keep the existing secrets rather than wiping them.
      const newSecrets = kvToRecord(secrets);
      if (Object.keys(newSecrets).length > 0) input.secrets = newSecrets;
      const saved = await updateConnector(row.id, input);
      if (saved.status === "failed") {
        setErr(saved.last_error || t('settings.connectors.save_failed'));
        return;
      }
      await onSaved();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : t('settings.connectors.save_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={t('settings.connectors.edit_modal_aria')}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4"
    >
      <form
        onSubmit={onSubmit}
        className="w-full max-w-md space-y-3 rounded-md bg-bg-elevated p-4 shadow-md"
      >
        <h3 className="text-base font-semibold text-text-primary">
          {t('settings.connectors.edit_modal_title')} — {row.provider_id}
        </h3>
        <p className="text-xs text-text-secondary">
          {t('settings.connectors.readonly_hint', { source: row.source, category: row.category })}
        </p>
        <label className="block text-xs text-text-secondary">
          {t('settings.connectors.display_name')}
          <input
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border-subtle bg-bg-base px-2 py-1 text-sm text-text-primary"
          />
        </label>
        <fieldset className="space-y-1">
          <legend className="text-xs text-text-secondary">
            {t('settings.connectors.secrets_legend')}
          </legend>
          {detail && detail.secret_keys.length > 0 ? (
            <p className="text-xs text-text-secondary">
              {t('settings.connectors.existing_secrets', {
                keys: detail.secret_keys.join(", "),
              })}
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
            {t('settings.connectors.add_secret')}
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
            {t('common.cancel')}
          </button>
          <button
            type="submit"
            disabled={submitting || loadingDetail || !detail}
            className="rounded-md bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"
          >
            {submitting ? t('common.saving') : t('common.save')}
          </button>
        </div>
      </form>
    </div>
  );
}
