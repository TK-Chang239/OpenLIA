import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { AddConnectorForm, type EditingConnector } from "./AddConnectorForm";
import {
  deleteConnector,
  getConnector,
  listBuiltinTemplates,
  listConnectors,
  syncTemplateSpecs,
  type BuiltinTemplate,
  type ConnectorRow,
} from "../../api/connectors";
import { refreshDeptHealth } from "../../store/dept-health";
import { saveProviders } from "../../api/setup";
import { ApiError } from "../../api/client";
import { CatalogGrid } from "../../components/connectors/CatalogGrid";
import { CategoryRequirementsPanel } from "../../components/connectors/CategoryRequirementsPanel";
import { InstallBuiltinForm } from "../../components/connectors/InstallBuiltinForm";
import { useDeptHealth } from "../../store/dept-health";

interface Props {
  totalSteps: number;
  onBack: () => void;
  onSaved: () => void;
}

export function ConnectorsStep({ totalSteps, onBack, onSaved }: Props) {
  const [rows, setRows] = useState<ConnectorRow[]>([]);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<EditingConnector | null>(null);
  const [catalog, setCatalog] = useState<BuiltinTemplate[] | null>(null);
  const [picking, setPicking] = useState(false);
  const [chosenTemplate, setChosenTemplate] = useState<BuiltinTemplate | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const r = await listConnectors();
      setRows(r);
      await refreshDeptHealth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connectors.");
    }
  };

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const onCreated = async (_row: ConnectorRow) => {
    setAdding(false);
    setEditing(null);
    await refresh();
  };

  const onEdit = async (id: string) => {
    try {
      const detail = await getConnector(id);
      setEditing({
        id: detail.id,
        providerId: detail.provider_id,
        displayName: detail.display_name,
        source: detail.source,
        category: detail.category,
        launch: detail.launch,
        secretKeys: detail.secret_keys,
        sourceRepoUrl: detail.source_repo_url ?? null,
        sourceRepoRevision: detail.source_repo_revision ?? null,
        groundingPaths: detail.grounding_paths ?? null,
        openapiUrl: detail.openapi_url ?? null,
      });
      setAdding(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load connector.");
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteConnector(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
    }
  };

  const onSyncSpecs = async (id: string) => {
    setError(null);
    try {
      await syncTemplateSpecs(id);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed.");
    }
  };

  const onNext = async () => {
    setLoading(true);
    setError(null);
    try {
      await saveProviders();
      onSaved();
    } catch (err) {
      setError(extractErrorMessage(err, "Failed to advance step."));
    } finally {
      setLoading(false);
    }
  };

  const canAdvance = rows.some((r) => r.status === "validated");
  const healths = useDeptHealth((s) => s.healths);

  return (
    <WizardShell
      title="Connectors"
      stepIndex={3}
      totalSteps={totalSteps}
      footer={
        <WizardFooter
          onBack={onBack}
          onNext={onNext}
          nextDisabled={!canAdvance}
          loading={loading}
        />
      }
    >
      <div className="space-y-6">
        <CategoryRequirementsPanel connectors={rows} healths={healths} />
        <section className="space-y-3">
          <header className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary">Connectors</h3>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={async () => {
                  if (catalog === null) setCatalog(await listBuiltinTemplates());
                  setPicking(true);
                }}
                className="inline-flex items-center gap-2 rounded-md bg-accent-primary px-3 py-1 text-xs text-text-on-accent"
              >
                Add from catalog
              </button>
              <button
                type="button"
                onClick={() => setAdding((v) => !v)}
                className="inline-flex items-center gap-2 rounded-md border border-dashed border-border-secondary px-3 py-1 text-xs text-text-secondary hover:text-text-primary"
              >
                <Plus size={14} />
                {adding ? "Cancel" : "Add custom connector"}
              </button>
            </div>
          </header>

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
              onInstalled={async (row) => {
                setChosenTemplate(null);
                await onCreated(row);
              }}
            />
          )}

          {adding ? (
            <AddConnectorForm
              onCancel={() => setAdding(false)}
              onCreated={onCreated}
            />
          ) : null}

          {error ? (
            <p role="alert" className="text-xs text-feedback-error">
              {error}
            </p>
          ) : null}

          {!canAdvance && rows.length > 0 ? (
            <p className="text-xs text-text-secondary" data-testid="next-disabled-hint">
              At least one connector must finish validating before you can
              continue.
            </p>
          ) : null}

          {rows.length === 0 ? (
            <p className="text-sm text-text-secondary">
              No connectors yet. Add one from the catalog or add a custom connector.
            </p>
          ) : (
            <ul className="space-y-2">
              {rows.map((r) => (
                <li
                  key={r.id}
                  className="rounded-md border border-border-subtle bg-bg-elevated p-3"
                  data-testid={`connector-row-${r.id}`}
                >
                  {editing && editing.id === r.id ? (
                    <AddConnectorForm
                      key={`edit-${editing.id}`}
                      onCancel={() => setEditing(null)}
                      onCreated={onCreated}
                      editing={editing}
                    />
                  ) : (
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-text-primary">
                          {r.display_name || r.provider_id}{" "}
                          <span className="text-xs text-text-secondary">
                            ({r.source} · {r.category})
                          </span>
                        </p>
                        <p className="text-xs text-text-secondary">
                          status: {r.status}
                        </p>
                        {r.last_error ? (
                          <ErrorDetails error={r.last_error} />
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <button
                          type="button"
                          onClick={() => onEdit(r.id)}
                          className="text-accent-primary hover:underline"
                        >
                          Edit
                        </button>
                        {r.source === "built_in" ? (
                          <button
                            type="button"
                            onClick={() => onSyncSpecs(r.id)}
                            title="Re-sync runner specs from the built-in template (use after upgrading OpenLIA)."
                            className="text-accent-primary hover:underline"
                          >
                            Sync specs
                          </button>
                        ) : null}
                        <button
                          type="button"
                          onClick={() => onDelete(r.id)}
                          className="text-feedback-error hover:underline"
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </WizardShell>
  );
}

function extractErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const body = err.body;
    if (body && typeof body === "object" && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      if (detail && typeof detail === "object" && "message" in detail) {
        const message = (detail as { message: unknown }).message;
        if (typeof message === "string") return message;
      }
    }
    return err.message;
  }
  return err instanceof Error ? err.message : fallback;
}

interface ErrorDetailsProps {
  error: string;
}

function ErrorDetails({ error }: ErrorDetailsProps) {
  const [expanded, setExpanded] = useState(false);
  const SUMMARY_LIMIT = 100;
  const isLong = error.length > SUMMARY_LIMIT || error.includes("\n");
  const summary = isLong
    ? `${error.replace(/\s+/g, " ").slice(0, SUMMARY_LIMIT)}...`
    : error;

  return (
    <div className="mt-1">
      <p className="text-xs text-feedback-error">
        Error: {expanded || !isLong ? null : summary}
        {isLong ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="ml-1 text-feedback-error underline hover:opacity-80"
          >
            {expanded ? "Hide details" : "Show details"}
          </button>
        ) : (
          <span>{error}</span>
        )}
      </p>
      {expanded && isLong ? (
        <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-md border border-border-subtle bg-bg-base px-2 py-1 font-mono text-[11px] text-feedback-error">
          {error}
        </pre>
      ) : null}
    </div>
  );
}
