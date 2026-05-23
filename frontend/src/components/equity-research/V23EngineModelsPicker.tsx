/**
 * V23EngineModelsPicker — composer-toolbar trigger + modal that lets the
 * user assign a model to each LLM-using stage of the v2.3 pipeline.
 *
 * Mirrors V2EngineModelsPicker but talks to the v2.3 endpoints and
 * lists the seven v2.3 LLM-using slots (VISUALIZE / ASSEMBLE are
 * deterministic and have no slot). Kept as a separate component so the
 * v2.3 engine stays fully independent of v1/v2.2.
 */
import * as Dialog from "@radix-ui/react-dialog";
import { AlertTriangle, Check, Cpu, X } from "lucide-react";
import { type JSX, useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  type AssignmentsResponse,
  V23_SLOTS,
  V23_SLOT_DESCRIPTION,
  V23_SLOT_LABEL,
  V23_SLOT_RECOMMENDATION,
  type V23Slot,
  getV23ModelAssignments,
  putV23ModelAssignments,
} from "../../api/er-v2-3-models";
import { type RosterEntry, getEnabledModels } from "../../api/settings";

interface Props {
  /** Called after each fetch + save with the authoritative snapshot. The
   *  parent uses this to decide whether to allow report dispatch. */
  onAssignmentsChange?: (snapshot: AssignmentsResponse) => void;
}

export function V23EngineModelsPicker({
  onAssignmentsChange,
}: Props): JSX.Element {
  const [models, setModels] = useState<RosterEntry[] | null>(null);
  const [saved, setSaved] = useState<AssignmentsResponse | null>(null);
  const [draft, setDraft] = useState<Partial<Record<V23Slot, string>>>({});
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const onAssignmentsChangeRef = useRef(onAssignmentsChange);
  onAssignmentsChangeRef.current = onAssignmentsChange;

  const propagate = useCallback((next: AssignmentsResponse) => {
    setSaved(next);
    setDraft(next.assignments);
    onAssignmentsChangeRef.current?.(next);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoadError(null);
    Promise.all([
      getEnabledModels().catch((e: unknown) => {
        if (!cancelled) {
          setLoadError(
            e instanceof Error ? e.message : "could not load /settings/models",
          );
        }
        return null;
      }),
      getV23ModelAssignments().catch(() => null),
    ]).then(([m, a]) => {
      if (cancelled) return;
      setModels(m ?? []);
      if (a) propagate(a);
    });
    return () => {
      cancelled = true;
    };
  }, [propagate]);

  const enabledModels = useMemo(
    () => (models ?? []).filter((m) => m.is_enabled),
    [models],
  );

  const total = V23_SLOTS.length;
  const assignedCount = V23_SLOTS.filter((s) => draft[s]).length;
  const savedAssignedCount = saved
    ? V23_SLOTS.filter((s) => saved.assignments[s]).length
    : 0;
  const allAssigned = assignedCount === total;
  const savedAllAssigned = savedAssignedCount === total;
  const dirty = saved
    ? JSON.stringify(draft) !== JSON.stringify(saved.assignments)
    : true;

  const triggerLabel = `Engine models · ${savedAssignedCount}/${total}`;

  const onSelectModel = (slot: V23Slot, modelId: string) => {
    setDraft((prev) => {
      const next = { ...prev };
      if (!modelId) {
        delete next[slot];
      } else {
        next[slot] = modelId;
      }
      return next;
    });
  };

  const cancel = () => {
    if (saved) setDraft(saved.assignments);
    setError(null);
    setOpen(false);
  };

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await putV23ModelAssignments(draft);
      propagate(next);
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Trigger asChild>
        <button
          type="button"
          aria-label="Configure per-stage v2.3 engine models"
          data-testid="er-v2-3-engine-models-trigger"
          className={[
            "inline-flex items-center gap-[6px] rounded-sm border px-2 py-[4px] font-mono text-[10px] uppercase tracking-[0.06em] transition-colors duration-normal ease-out",
            savedAllAssigned
              ? "border-[--color-border-subtle] bg-[--color-bg-base] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary]"
              : "border-[--color-feedback-warning] bg-[rgba(255,180,0,0.06)] text-[--color-feedback-warning] hover:bg-[rgba(255,180,0,0.10)]",
          ].join(" ")}
        >
          {savedAllAssigned ? (
            <Cpu size={10} strokeWidth={1.5} aria-hidden />
          ) : (
            <AlertTriangle size={10} strokeWidth={2} aria-hidden />
          )}
          <span>{triggerLabel}</span>
        </button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-[rgba(13,13,11,0.55)]" />
        <Dialog.Content
          data-testid="er-v2-3-engine-models-modal"
          className="fixed left-1/2 top-1/2 z-[60] flex max-h-[86vh] w-full max-w-[640px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
          aria-describedby={undefined}
        >
          <div className="flex items-center gap-[10px] border-b border-[--color-border-subtle] px-[22px] py-[16px]">
            <Cpu size={15} strokeWidth={1.9} aria-hidden className="text-[--color-text-secondary]" />
            <div className="flex min-w-0 flex-1 flex-col">
              <Dialog.Title className="m-0 truncate text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
                Engine model assignments
              </Dialog.Title>
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                {assignedCount}/{total} slots assigned · v2.3 pipeline
              </span>
            </div>
            <Dialog.Close asChild>
              <button
                type="button"
                aria-label="Close"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
              >
                <X size={14} strokeWidth={2} />
              </button>
            </Dialog.Close>
          </div>

          {loadError ? (
            <div className="flex flex-col items-start gap-[8px] px-[22px] py-[18px] text-[13px] text-[--color-text-secondary]">
              <span className="font-medium text-[--color-feedback-danger]">
                Could not load configured models.
              </span>
              <span className="font-mono text-[11.5px] text-[--color-text-tertiary]">
                {loadError}
              </span>
            </div>
          ) : enabledModels.length === 0 ? (
            <div className="flex flex-col items-start gap-[8px] px-[22px] py-[18px] text-[13px] text-[--color-text-secondary]">
              <span className="font-medium text-[--color-feedback-warning]">
                No enabled models found.
              </span>
              <span>
                Visit Settings → Models to configure at least one model
                before you can assign it to a pipeline stage.
              </span>
            </div>
          ) : (
            <div className="flex-1 overflow-auto px-[22px] py-[14px]">
              <ul className="flex flex-col gap-[12px]">
                {V23_SLOTS.map((slot) => {
                  const selected = draft[slot] ?? "";
                  const isMissing = !selected;
                  return (
                    <li
                      key={slot}
                      className={[
                        "rounded-[9px] border px-[12px] py-[10px]",
                        isMissing
                          ? "border-[rgba(255,180,0,0.35)] bg-[rgba(255,180,0,0.04)]"
                          : "border-[--color-border-subtle] bg-[--color-bg-base]",
                      ].join(" ")}
                    >
                      <div className="mb-[6px] flex items-center justify-between gap-[10px]">
                        <div className="flex min-w-0 flex-1 flex-col">
                          <span className="text-[13px] font-medium text-[--color-text-primary]">
                            {V23_SLOT_LABEL[slot]}
                          </span>
                          <span className="text-[11.5px] leading-[1.45] text-[--color-text-secondary]">
                            {V23_SLOT_DESCRIPTION[slot]}
                          </span>
                        </div>
                        {isMissing ? (
                          <span className="inline-flex shrink-0 items-center gap-[4px] rounded-full border border-[rgba(255,180,0,0.35)] bg-[rgba(255,180,0,0.10)] px-[7px] py-[1px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-feedback-warning]">
                            <AlertTriangle size={9} strokeWidth={2.4} />
                            unset
                          </span>
                        ) : (
                          <span className="inline-flex shrink-0 items-center gap-[4px] rounded-full border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[7px] py-[1px] font-mono text-[9px] uppercase tracking-[0.1em] text-[--color-feedback-success]">
                            <Check size={9} strokeWidth={2.4} />
                            set
                          </span>
                        )}
                      </div>
                      <select
                        value={selected}
                        onChange={(e) => onSelectModel(slot, e.target.value)}
                        data-testid={`er-v2-3-slot-${slot}`}
                        className="h-[30px] w-full rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[8px] font-mono text-[11.5px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
                      >
                        <option value="">— choose a model —</option>
                        {enabledModels.map((m) => (
                          <option key={m.id} value={m.id}>
                            {m.display_name} · {m.provider_kind}
                          </option>
                        ))}
                      </select>
                      <p className="mt-[6px] flex items-start gap-[6px] text-[11px] leading-[1.5] text-[--color-text-tertiary]">
                        <span
                          aria-hidden="true"
                          className="mt-[2px] inline-block shrink-0 rounded-sm border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[4px] py-0 font-mono text-[8.5px] uppercase tracking-[0.1em] text-[--color-text-secondary]"
                        >
                          rec
                        </span>
                        <span>{V23_SLOT_RECOMMENDATION[slot]}</span>
                      </p>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}

          {error ? (
            <div
              role="alert"
              className="mx-[22px] mb-[10px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-[10px] py-[8px] text-[12px] text-[--color-feedback-danger]"
            >
              {error}
            </div>
          ) : null}

          <div className="flex items-center justify-between gap-[10px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[12px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {allAssigned ? "ready to run" : `${total - assignedCount} slot(s) still unset`}
            </span>
            <div className="flex items-center gap-[8px]">
              <button
                type="button"
                onClick={cancel}
                className="inline-flex h-8 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-3 font-display text-[13px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={save}
                disabled={busy || !dirty}
                className="inline-flex h-8 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
