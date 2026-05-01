import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { WizardShell } from "../WizardShell";
import { WizardFooter } from "../WizardFooter";
import { AddConnectorForm, type EditingConnector } from "./AddConnectorForm";
import { PerNeedReviewCard } from "./PerNeedReviewCard";
import {
  deleteConnector,
  getConnector,
  listConnectors,
  listProposedSpecs,
  reResolveSpecs,
  validateConnector,
  type ConnectorRow,
  type ProposedSpec,
} from "../../api/connectors";
import { refreshDeptHealth } from "../../store/dept-health";
import { saveProviders } from "../../api/setup";
import { ApiError } from "../../api/client";

interface Props {
  totalSteps: number;
  onBack: () => void;
  onSaved: () => void;
}

interface ConnectorReviewState {
  proposals: ProposedSpec[];
  loading: boolean;
  error: string | null;
}

export function ConnectorsStep({ totalSteps, onBack, onSaved }: Props) {
  const [rows, setRows] = useState<ConnectorRow[]>([]);
  const [adding, setAdding] = useState(false);
  const [editing, setEditing] = useState<EditingConnector | null>(null);
  const [activeReview, setActiveReview] = useState<string | null>(null);
  const [reviewByConnector, setReviewByConnector] = useState<
    Record<string, ConnectorReviewState>
  >({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [validatingId, setValidatingId] = useState<string | null>(null);
  const [validatedFlash, setValidatedFlash] = useState<{
    id: string;
    status: "validated" | "failed";
  } | null>(null);

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

  const onCreated = async (row: ConnectorRow) => {
    setAdding(false);
    setEditing(null);
    await refresh();
    // Fetch initial proposals (may be empty in Phase 6 stub).
    await loadProposalsFor(row.id);
    setActiveReview(row.id);
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

  const loadProposalsFor = async (connectorId: string) => {
    setReviewByConnector((prev) => ({
      ...prev,
      [connectorId]: { proposals: [], loading: true, error: null },
    }));
    try {
      const proposals = await listProposedSpecs(connectorId);
      setReviewByConnector((prev) => ({
        ...prev,
        [connectorId]: { proposals, loading: false, error: null },
      }));
    } catch (err) {
      setReviewByConnector((prev) => ({
        ...prev,
        [connectorId]: {
          proposals: [],
          loading: false,
          error: err instanceof Error ? err.message : "Failed to load proposals.",
        },
      }));
    }
  };

  const onResolveAgain = async (connectorId: string) => {
    setReviewByConnector((prev) => ({
      ...prev,
      [connectorId]: {
        ...(prev[connectorId] ?? { proposals: [], error: null }),
        loading: true,
      } as ConnectorReviewState,
    }));
    try {
      const proposals = await reResolveSpecs(connectorId);
      setReviewByConnector((prev) => ({
        ...prev,
        [connectorId]: { proposals, loading: false, error: null },
      }));
    } catch (err) {
      setReviewByConnector((prev) => ({
        ...prev,
        [connectorId]: {
          proposals: prev[connectorId]?.proposals ?? [],
          loading: false,
          error: err instanceof Error ? err.message : "Re-resolve failed.",
        },
      }));
    }
  };

  const onValidate = async (id: string) => {
    setValidatingId(id);
    setValidatedFlash(null);
    try {
      const updated = await validateConnector(id);
      await refresh();
      setValidatedFlash({
        id,
        status: updated.status === "validated" ? "validated" : "failed",
      });
      window.setTimeout(() => {
        setValidatedFlash((cur) => (cur && cur.id === id ? null : cur));
      }, 4000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed.");
    } finally {
      setValidatingId((cur) => (cur === id ? null : cur));
    }
  };

  const onDelete = async (id: string) => {
    try {
      await deleteConnector(id);
      await refresh();
      setReviewByConnector((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (activeReview === id) setActiveReview(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed.");
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
        <section>
          <header className="mb-2">
            <h3 className="text-sm font-medium text-text-primary">
              Built-in templates
            </h3>
            <p className="text-xs text-text-secondary">
              No built-in templates available — add a custom connector below.
            </p>
          </header>
        </section>

        <section className="space-y-3">
          <header className="flex items-center justify-between">
            <h3 className="text-sm font-medium text-text-primary">Connectors</h3>
            <button
              type="button"
              onClick={() => setAdding((v) => !v)}
              className="inline-flex items-center gap-2 rounded-md border border-dashed border-border-secondary px-3 py-1 text-xs text-text-secondary hover:text-text-primary"
            >
              <Plus size={14} />
              {adding ? "Cancel" : "Add custom connector"}
            </button>
          </header>

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
              Click Validate on at least one connector to continue.
            </p>
          ) : null}

          {rows.length === 0 ? (
            <p className="text-sm text-text-secondary">
              No connectors yet. Click "Add custom connector" to add one.
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
                        {validatedFlash && validatedFlash.id === r.id ? (
                          <p
                            className={`mt-1 text-xs ${
                              validatedFlash.status === "validated"
                                ? "text-feedback-success"
                                : "text-feedback-error"
                            }`}
                            role="status"
                          >
                            {validatedFlash.status === "validated"
                              ? "Validated successfully."
                              : "Validation failed — see status above."}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex items-center gap-2 text-xs">
                        <button
                          type="button"
                          onClick={() => onValidate(r.id)}
                          disabled={validatingId === r.id}
                          className="text-accent-primary hover:underline disabled:opacity-50"
                        >
                          {validatingId === r.id ? "Validating..." : "Validate"}
                        </button>
                        <button
                          type="button"
                          onClick={() => onEdit(r.id)}
                          className="text-accent-primary hover:underline"
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setActiveReview(r.id);
                            void loadProposalsFor(r.id);
                          }}
                          className="text-accent-primary hover:underline"
                        >
                          Review specs
                        </button>
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

                  {activeReview === r.id ? (
                    <ReviewPane
                      connectorId={r.id}
                      state={
                        reviewByConnector[r.id] ?? {
                          proposals: [],
                          loading: false,
                          error: null,
                        }
                      }
                      onChanged={() => loadProposalsFor(r.id)}
                      onResolveAll={() => onResolveAgain(r.id)}
                    />
                  ) : null}
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

interface ReviewPaneProps {
  connectorId: string;
  state: ConnectorReviewState;
  onChanged: () => void;
  onResolveAll: () => void;
}

function ReviewPane({ connectorId, state, onChanged, onResolveAll }: ReviewPaneProps) {
  return (
    <div className="mt-3 space-y-2 border-t border-border-subtle pt-3">
      <div className="flex items-center justify-between">
        <h5 className="text-xs font-medium text-text-primary">
          Per-need proposals
        </h5>
        <button
          type="button"
          onClick={onResolveAll}
          className="text-xs text-accent-primary hover:underline"
        >
          Re-resolve all
        </button>
      </div>
      {state.loading ? (
        <p className="text-xs text-text-secondary">Loading...</p>
      ) : null}
      {state.error ? (
        <p role="alert" className="text-xs text-feedback-error">
          {state.error}
        </p>
      ) : null}
      {!state.loading && state.proposals.length === 0 ? (
        <p className="text-xs text-text-secondary">No proposals at this time.</p>
      ) : null}
      {state.proposals.map((p) => (
        <PerNeedReviewCard
          key={`${p.department_id}-${p.need_id}`}
          connectorId={connectorId}
          proposal={p}
          onChanged={onChanged}
        />
      ))}
    </div>
  );
}
