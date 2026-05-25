/**
 * V23ReportSettingsModal — the v2.3-flavoured "Report Settings" pill.
 *
 * v2.2 organised templates beneath three modes (stock_initiation,
 * stock_update, sector_research). v2.3 retired modes — every report
 * type is a peer template (initiation, update, sector_research,
 * morning_brief, earnings_review) and user-uploaded templates are
 * first-class siblings of those built-ins. This modal renders that
 * flat list as one radio group, plus a length picker and an "Upload"
 * trigger that opens the V23TemplateUploadModal (md / json / docx).
 *
 * The caller owns the selection state and the upload-modal open flag —
 * this component is purely presentational.
 */
import { Check, Plus, Upload, X } from "lucide-react";
import { type JSX, useEffect, useState } from "react";

import {
  fetchV23Builtins,
  listReportTemplates,
  type ReportTemplate,
  type V23BuiltinTemplate,
} from "../../api/report-templates";

export type V23ReportType = V23BuiltinTemplate["report_type"];
export type V23ReportLength = "concise" | "normal" | "elaborative";
// 3-state UI value. "off" maps to null on the wire; "medium" / "high"
// forward verbatim to the v2.3 stream endpoint.
export type V23ReasoningEffort = "off" | "medium" | "high";

export interface V23SettingsSelection {
  /** The user-uploaded template's row id, or null when a built-in is
   *  active. When non-null, `reportType` is the suggested clarifier
   *  context (the engine resolves `template_id` directly). */
  templateId: string | null;
  /** The v2.3 ReportType. For built-ins this matches the built-in
   *  selected; for user templates it defaults to "initiation" unless
   *  the caller overrides. */
  reportType: V23ReportType;
}

export interface V23ReportSettingsModalProps {
  open: boolean;
  selection: V23SettingsSelection;
  length: V23ReportLength;
  reasoningEffort: V23ReasoningEffort;
  onSelectionChange: (next: V23SettingsSelection) => void;
  onLengthChange: (next: V23ReportLength) => void;
  onReasoningEffortChange: (next: V23ReasoningEffort) => void;
  onUploadClick: () => void;
  onClose: () => void;
  /** Bump this to force the template list to refetch — used by the
   *  page after an upload completes so the new row shows up without
   *  remounting the modal. */
  refreshKey?: number;
}

const LENGTH_LABELS: Record<V23ReportLength, string> = {
  concise: "Concise",
  normal: "Normal",
  elaborative: "Elaborative",
};

const REASONING_LABELS: Record<V23ReasoningEffort, string> = {
  off: "Off",
  medium: "Medium",
  high: "High",
};

export function V23ReportSettingsModal({
  open,
  selection,
  length,
  reasoningEffort,
  onSelectionChange,
  onLengthChange,
  onReasoningEffortChange,
  onUploadClick,
  onClose,
  refreshKey = 0,
}: V23ReportSettingsModalProps): JSX.Element | null {
  const [builtins, setBuiltins] = useState<V23BuiltinTemplate[] | null>(null);
  const [userTemplates, setUserTemplates] = useState<ReportTemplate[] | null>(
    null,
  );
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoadError(null);
    Promise.all([fetchV23Builtins(), listReportTemplates()])
      .then(([b, t]) => {
        if (cancelled) return;
        setBuiltins(b);
        setUserTemplates(t);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setLoadError(e instanceof Error ? e.message : "failed to load templates");
        setBuiltins([]);
        setUserTemplates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, refreshKey]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  function pickBuiltin(b: V23BuiltinTemplate): void {
    onSelectionChange({
      templateId: null,
      reportType: b.report_type,
    });
  }

  function pickUserTemplate(row: ReportTemplate): void {
    onSelectionChange({
      templateId: row.id,
      // User templates don't carry a report_type — default to initiation
      // so the engine still has a clarifier-context anchor.
      reportType: "initiation",
    });
  }

  const isBuiltinActive = (b: V23BuiltinTemplate) =>
    selection.templateId === null && selection.reportType === b.report_type;
  const isUserTemplateActive = (row: ReportTemplate) =>
    selection.templateId === row.id;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="er-v2-3-settings-title"
      data-testid="er-v2-3-settings-modal"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        data-testid="er-v2-3-settings-backdrop"
        className="absolute inset-0 bg-black/40"
        onClick={onClose}
      />
      <div className="relative z-10 mx-4 flex max-h-[88vh] w-full max-w-[560px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]">
        <header className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[18px]">
          <h2
            id="er-v2-3-settings-title"
            className="m-0 text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            Report settings
          </h2>
          <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
            v2.3
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            data-testid="er-v2-3-settings-close"
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </header>

        <div className="flex-1 overflow-y-auto">
          <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              Length
            </span>
            <div
              role="radiogroup"
              aria-label="Report length"
              className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
            >
              {(Object.keys(LENGTH_LABELS) as V23ReportLength[]).map((l) => {
                const active = l === length;
                return (
                  <button
                    key={l}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => onLengthChange(l)}
                    data-testid={`er-v2-3-settings-length-${l}`}
                    className={[
                      "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
                      active
                        ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                        : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
                    ].join(" ")}
                  >
                    {LENGTH_LABELS[l]}
                  </button>
                );
              })}
            </div>
          </section>

          <section
            className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
            data-testid="er-v2-3-settings-reasoning"
          >
            <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              Reasoning
            </span>
            <div
              role="radiogroup"
              aria-label="Reasoning effort"
              className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
            >
              {(Object.keys(REASONING_LABELS) as V23ReasoningEffort[]).map((r) => {
                const active = r === reasoningEffort;
                return (
                  <button
                    key={r}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => onReasoningEffortChange(r)}
                    data-testid={`er-v2-3-settings-reasoning-${r}`}
                    className={[
                      "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
                      active
                        ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                        : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
                    ].join(" ")}
                  >
                    {REASONING_LABELS[r]}
                  </button>
                );
              })}
            </div>
            <p className="mt-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
              Extended thinking applies to the planning and synthesis stages only. Off
              is fastest; Medium adds deliberation for trickier reports; High burns
              more tokens and time for the deepest analysis.
            </p>
          </section>

          <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <div className="mb-[10px] flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
                Template
              </span>
              <button
                type="button"
                onClick={onUploadClick}
                data-testid="er-v2-3-settings-upload"
                className="inline-flex h-7 items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[11px] font-display text-[12px] text-[--color-text-secondary] transition-all hover:border-solid hover:border-[--color-feedback-success] hover:bg-[rgba(212,255,0,0.05)] hover:text-[--color-feedback-success]"
              >
                <Upload size={11} strokeWidth={2} />
                Upload template
              </button>
            </div>

            {loadError ? (
              <div
                role="alert"
                data-testid="er-v2-3-settings-load-error"
                className="mb-3 rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
              >
                {loadError}
              </div>
            ) : null}

            <div className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
              Built-ins
            </div>
            <ul
              role="radiogroup"
              aria-label="Built-in templates"
              data-testid="er-v2-3-settings-builtins"
              className="m-0 flex list-none flex-col p-0"
            >
              {builtins === null ? (
                <li className="py-[9px] text-[12px] text-[--color-text-secondary]">
                  Loading…
                </li>
              ) : (
                builtins.map((b) => (
                  <BuiltinRow
                    key={b.report_type}
                    builtin={b}
                    active={isBuiltinActive(b)}
                    onPick={() => pickBuiltin(b)}
                  />
                ))
              )}
            </ul>

            <div className="mt-4 mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
              <span>Your templates</span>
              {userTemplates !== null ? (
                <span className="text-[--color-text-tertiary]/70">
                  ({userTemplates.length})
                </span>
              ) : null}
            </div>
            <ul
              role="radiogroup"
              aria-label="User templates"
              data-testid="er-v2-3-settings-user-templates"
              className="m-0 flex list-none flex-col p-0"
            >
              {userTemplates === null ? (
                <li className="py-[9px] text-[12px] text-[--color-text-secondary]">
                  Loading…
                </li>
              ) : userTemplates.length === 0 ? (
                <li className="py-[9px] text-[12px] text-[--color-text-secondary]">
                  No uploads yet. Use{" "}
                  <button
                    type="button"
                    onClick={onUploadClick}
                    className="inline-flex items-center gap-[4px] text-[--color-text-primary] underline-offset-2 hover:underline"
                  >
                    <Plus size={11} /> upload template
                  </button>{" "}
                  to add one.
                </li>
              ) : (
                userTemplates.map((row) => (
                  <UserTemplateRow
                    key={row.id}
                    row={row}
                    active={isUserTemplateActive(row)}
                    onPick={() => pickUserTemplate(row)}
                  />
                ))
              )}
            </ul>
          </section>
        </div>

        <div className="flex justify-end gap-2 rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[14px]">
          <button
            type="button"
            onClick={onClose}
            data-testid="er-v2-3-settings-done"
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover]"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}

interface BuiltinRowProps {
  builtin: V23BuiltinTemplate;
  active: boolean;
  onPick: () => void;
}

function BuiltinRow({ builtin, active, onPick }: BuiltinRowProps): JSX.Element {
  return (
    <li
      role="radio"
      aria-checked={active}
      tabIndex={0}
      onClick={onPick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onPick();
        }
      }}
      data-testid={`er-v2-3-settings-builtin-${builtin.report_type}`}
      className="group flex cursor-pointer items-start gap-[10px] border-b border-dashed border-[--color-border-subtle] py-[9px] last:border-b-0"
    >
      <span
        aria-hidden="true"
        className={[
          "mt-[2px] inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors",
          active
            ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
            : "border-[--color-border-strong]",
        ].join(" ")}
      >
        {active ? <Check size={10} strokeWidth={3} /> : null}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[13.5px] text-[--color-text-primary] transition-colors group-hover:text-[--color-feedback-success]">
          {builtin.template_spec.name}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          {builtin.report_type.replace(/_/g, " ")}
          {builtin.template_spec.ticker_anchored ? " · ticker" : " · thematic"}
        </span>
        {builtin.template_spec.shape_description ? (
          <span className="mt-[2px] text-[12px] leading-[1.4] text-[--color-text-secondary]">
            {builtin.template_spec.shape_description}
          </span>
        ) : null}
      </span>
    </li>
  );
}

interface UserTemplateRowProps {
  row: ReportTemplate;
  active: boolean;
  onPick: () => void;
}

function UserTemplateRow({
  row,
  active,
  onPick,
}: UserTemplateRowProps): JSX.Element {
  // The user-template spec dict may or may not look v2.3-shaped — pull
  // shape_description / sections defensively so this works for both
  // v2-shaped and v2.3-shaped rows. v2-shaped rows still render; they
  // 422 at run-launch with a useful error.
  const spec = row.template_spec as Record<string, unknown>;
  const shape =
    typeof spec.shape_description === "string" ? spec.shape_description : null;
  const sectionsCount = Array.isArray(spec.sections) ? spec.sections.length : 0;
  return (
    <li
      role="radio"
      aria-checked={active}
      tabIndex={0}
      onClick={onPick}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onPick();
        }
      }}
      data-testid={`er-v2-3-settings-user-template-${row.id}`}
      className="group flex cursor-pointer items-start gap-[10px] border-b border-dashed border-[--color-border-subtle] py-[9px] last:border-b-0"
    >
      <span
        aria-hidden="true"
        className={[
          "mt-[2px] inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border-[1.5px] transition-colors",
          active
            ? "border-[--color-accent-primary] bg-[--color-accent-primary] text-[--color-accent-on]"
            : "border-[--color-border-strong]",
        ].join(" ")}
      >
        {active ? <Check size={10} strokeWidth={3} /> : null}
      </span>
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="text-[13.5px] text-[--color-text-primary] transition-colors group-hover:text-[--color-feedback-success]">
          {row.name}
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
          custom · {sectionsCount} section{sectionsCount === 1 ? "" : "s"}
        </span>
        {shape ? (
          <span className="mt-[2px] text-[12px] leading-[1.4] text-[--color-text-secondary]">
            {shape}
          </span>
        ) : null}
      </span>
    </li>
  );
}
