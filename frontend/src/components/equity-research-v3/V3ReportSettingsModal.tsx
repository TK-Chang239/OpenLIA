/**
 * V3ReportSettingsModal — v3 equivalent of the v2 ReportSettingsModal.
 *
 * Same visual structure as ``components/equity-research/ReportSettingsModal``
 * (Radix dialog, segmented controls, section dividers, footer with
 * Cancel/Save buttons) so the v3 page chrome matches v1/v2 pixel-for-
 * pixel. v3-specific dials only — reasoning effort and template
 * picker render as disabled placeholder sections so the visual slot
 * exists today and PR2/PR3 just need to drop in the working
 * controls without re-laying-out the modal.
 *
 * Settings state is staged locally; ``onSave`` fires only on Save
 * (matches v2 behaviour, where Cancel reverts to the modal-open
 * snapshot of config).
 */
import * as Dialog from "@radix-ui/react-dialog";
import { Trash, Upload, X } from "lucide-react";
import { type JSX, useEffect, useState } from "react";

import { ApiError } from "../../api/_request";
import {
  FREEFORM_TEMPLATE_ID,
  type V3InstructionsSummary,
  type V3Language,
  type V3ReasoningEffort,
  type V3ReportLength,
  type V3TemplateSummary,
  deleteV3Instructions,
  deleteV3Template,
  listV3Instructions,
  listV3Templates,
} from "../../api/equity-research-v3";

export interface V3SettingsValue {
  length: V3ReportLength;
  language: V3Language;
  reasoningEffort: V3ReasoningEffort;
  /** Active template id. Built-ins use their seeded id
   *  (``initiation_default`` etc.); user uploads use a UUID hex. The
   *  sentinel ``FREEFORM_TEMPLATE_ID`` means "No template". */
  templateId: string;
  /** Cached display name so the page can render the mode pill
   *  without re-fetching the templates list. */
  templateName: string;
  /** Active instruction-profile id, or null when none is selected. */
  instructionsId: string | null;
  /** Cached profile name for the mode pill; null when none. */
  instructionsName: string | null;
}

interface Props {
  open: boolean;
  value: V3SettingsValue;
  onClose: () => void;
  onSave: (next: V3SettingsValue) => void;
  /** Bumped by the parent after a successful upload so the template
   *  list refetches without remounting the modal. */
  templatesRefreshKey?: number;
  /** Fires when the user clicks "Upload template" — the parent owns
   *  the upload modal so we don't nest dialogs. */
  onUploadClick: () => void;
  /** Bumped by the parent after a successful instructions upload so
   *  the profile list refetches without remounting the modal. */
  instructionsRefreshKey?: number;
  /** Fires when the user clicks "Upload instructions". */
  onUploadInstructionsClick: () => void;
}

const LENGTH_OPTIONS: { value: V3ReportLength; label: string }[] = [
  { value: "concise", label: "Concise" },
  { value: "normal", label: "Normal" },
  { value: "elaborative", label: "Elaborative" },
];

const LANGUAGE_OPTIONS: { value: V3Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "zh-TW", label: "繁體中文" },
];

const REASONING_OPTIONS: { value: V3ReasoningEffort; label: string }[] = [
  { value: "off", label: "Off" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
];

interface SegmentedProps<T extends string> {
  ariaLabel: string;
  value: T;
  options: { value: T; label: string }[];
  onChange: (next: T) => void;
}

function Segmented<T extends string>({
  ariaLabel,
  value,
  options,
  onChange,
}: SegmentedProps<T>): JSX.Element {
  return (
    <div
      role="radiogroup"
      aria-label={ariaLabel}
      className="flex gap-[2px] rounded-lg border border-[--color-border-subtle] bg-[--color-bg-base] p-[3px]"
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(opt.value)}
            className={[
              "flex-1 rounded-md px-[10px] py-2 text-center font-display text-[12.5px] transition-colors",
              active
                ? "bg-[--color-bg-elevated] font-medium text-[--color-text-primary] shadow-[0_1px_2px_rgba(13,13,11,0.06)]"
                : "text-[--color-text-secondary] hover:text-[--color-text-primary]",
            ].join(" ")}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}

function SectionHeader({ label }: { label: string }): JSX.Element {
  return (
    <span className="mb-[10px] block font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
      {label}
    </span>
  );
}

export function V3ReportSettingsModal({
  open,
  value,
  onClose,
  onSave,
  templatesRefreshKey = 0,
  onUploadClick,
  instructionsRefreshKey = 0,
  onUploadInstructionsClick,
}: Props): JSX.Element {
  const [length, setLength] = useState<V3ReportLength>(value.length);
  const [language, setLanguage] = useState<V3Language>(value.language);
  const [reasoningEffort, setReasoningEffort] = useState<V3ReasoningEffort>(
    value.reasoningEffort,
  );
  const [templateId, setTemplateId] = useState<string>(value.templateId);
  const [templateName, setTemplateName] = useState<string>(value.templateName);
  const [templates, setTemplates] = useState<V3TemplateSummary[] | null>(null);
  const [templatesError, setTemplatesError] = useState<string | null>(null);
  const [instructionsId, setInstructionsId] = useState<string | null>(
    value.instructionsId,
  );
  const [instructionsName, setInstructionsName] = useState<string | null>(
    value.instructionsName,
  );
  const [instructions, setInstructions] = useState<V3InstructionsSummary[] | null>(
    null,
  );
  const [instructionsError, setInstructionsError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setLength(value.length);
    setLanguage(value.language);
    setReasoningEffort(value.reasoningEffort);
    setTemplateId(value.templateId);
    setTemplateName(value.templateName);
    setInstructionsId(value.instructionsId);
    setInstructionsName(value.instructionsName);
  }, [
    open,
    value.length,
    value.language,
    value.reasoningEffort,
    value.templateId,
    value.templateName,
    value.instructionsId,
    value.instructionsName,
  ]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setTemplatesError(null);
    listV3Templates()
      .then((rows) => {
        if (!cancelled) setTemplates(rows);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 503) {
          setTemplatesError("v3 engine disabled on the server.");
        } else {
          setTemplatesError(
            err instanceof Error ? err.message : "Failed to load templates",
          );
        }
        setTemplates([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, templatesRefreshKey]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setInstructionsError(null);
    listV3Instructions()
      .then((rows) => {
        if (!cancelled) setInstructions(rows);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 503) {
          setInstructionsError("v3 engine disabled on the server.");
        } else {
          setInstructionsError(
            err instanceof Error ? err.message : "Failed to load instructions",
          );
        }
        setInstructions([]);
      });
    return () => {
      cancelled = true;
    };
  }, [open, instructionsRefreshKey]);

  const handleDelete = async (id: string) => {
    try {
      await deleteV3Template(id);
      setTemplates((prev) => prev?.filter((t) => t.id !== id) ?? null);
      // If the deleted row was the active selection, fall back to the
      // first built-in (initiation_default) so the picker always has a
      // valid selection on close.
      if (templateId === id) {
        const fallback = (templates ?? []).find(
          (t) => t.is_builtin && t.id !== id,
        );
        if (fallback) {
          setTemplateId(fallback.id);
          setTemplateName(fallback.name);
        }
      }
    } catch (err) {
      setTemplatesError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const pickTemplate = (row: V3TemplateSummary) => {
    setTemplateId(row.id);
    setTemplateName(row.name);
  };

  const pickNoTemplate = () => {
    setTemplateId(FREEFORM_TEMPLATE_ID);
    setTemplateName("No template");
  };

  const pickInstructions = (row: V3InstructionsSummary | null) => {
    setInstructionsId(row?.id ?? null);
    setInstructionsName(row?.name ?? null);
  };

  const handleDeleteInstructions = async (id: string) => {
    try {
      await deleteV3Instructions(id);
      setInstructions((prev) => prev?.filter((i) => i.id !== id) ?? null);
      if (instructionsId === id) {
        setInstructionsId(null);
        setInstructionsName(null);
      }
    } catch (err) {
      setInstructionsError(err instanceof Error ? err.message : "Delete failed");
    }
  };

  const isFreeform = templateId === FREEFORM_TEMPLATE_ID;
  // A freeform run has no shape without an instruction profile; block
  // Save so the user can't dispatch a run the server would 400.
  const freeformNeedsInstructions = isFreeform && !instructionsId;

  const save = () => {
    if (freeformNeedsInstructions) return;
    onSave({
      length,
      language,
      reasoningEffort,
      templateId,
      templateName,
      instructionsId,
      instructionsName,
    });
    onClose();
  };

  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-[rgba(13,13,11,0.45)]" />
        <Dialog.Content
          data-testid="er-v3-settings-modal"
          aria-describedby={undefined}
          className="fixed left-1/2 top-1/2 z-50 flex max-h-[88vh] w-full max-w-[520px] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        >
          <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[18px]">
            <Dialog.Title className="m-0 text-[16px] font-semibold tracking-[-0.005em] text-[--color-text-primary]">
              Report settings
            </Dialog.Title>
            <span className="ml-3 font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              v3 engine
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              <X size={14} strokeWidth={2} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto">
            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <SectionHeader label="Length" />
              <Segmented
                ariaLabel="Length"
                value={length}
                options={LENGTH_OPTIONS}
                onChange={setLength}
              />
            </section>

            <section className="border-b border-[--color-border-subtle] px-[22px] py-[18px]">
              <SectionHeader label="Language" />
              <Segmented
                ariaLabel="Language"
                value={language}
                options={LANGUAGE_OPTIONS}
                onChange={setLanguage}
              />
            </section>

            <section
              className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
              data-testid="er-v3-reasoning-effort"
            >
              <SectionHeader label="Reasoning effort" />
              <Segmented
                ariaLabel="Reasoning effort"
                value={reasoningEffort}
                options={REASONING_OPTIONS}
                onChange={setReasoningEffort}
              />
              <p className="mt-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
                Off keeps the run lean. Medium and High enable extended
                thinking on supported models (Anthropic Claude 4.x,
                OpenAI gpt-5 / o-series, Gemini 2.x). Higher effort
                buys deeper synthesis at the cost of more tokens and
                longer wall time.
              </p>
            </section>

            <section
              className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
              data-testid="er-v3-template-picker"
            >
              <div className="mb-[10px] flex items-center justify-between">
                <SectionHeader label="Template" />
                <button
                  type="button"
                  onClick={onUploadClick}
                  data-testid="er-v3-template-upload-trigger"
                  className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[3px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success]"
                >
                  <Upload size={11} strokeWidth={2} />
                  Upload
                </button>
              </div>
              <p className="mb-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
                A template is the report's outline — the sections it includes
                and the order they appear in, like a fill-in-the-blanks
                document. Upload your own, or pick No template below to let the
                analyst design the layout itself.
              </p>
              <button
                type="button"
                onClick={pickNoTemplate}
                data-testid="er-v3-template-option-freeform"
                className={[
                  "mb-[6px] flex w-full flex-col rounded-md border px-3 py-2 text-left",
                  isFreeform
                    ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
                    : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
                ].join(" ")}
              >
                <span className="text-[12.5px] font-medium text-[--color-text-primary]">
                  No template
                </span>
                <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                  instructions only — analyst designs the structure
                </span>
              </button>
              {templates === null ? (
                <p className="text-[12px] text-[--color-text-tertiary]">
                  Loading templates…
                </p>
              ) : templatesError ? (
                <p className="text-[12px] text-[--color-feedback-danger]">
                  {templatesError}
                </p>
              ) : templates.length === 0 ? (
                <p className="text-[12px] text-[--color-text-tertiary]">
                  No templates available.
                </p>
              ) : (
                <ul className="flex flex-col gap-[4px]">
                  {templates.map((t) => {
                    const active = templateId === t.id;
                    return (
                      <li key={t.id}>
                        <div
                          className={[
                            "flex items-center gap-2 rounded-md border px-3 py-2",
                            active
                              ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
                              : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
                          ].join(" ")}
                        >
                          <button
                            type="button"
                            onClick={() => pickTemplate(t)}
                            data-testid={`er-v3-template-option-${t.id}`}
                            className="flex min-w-0 flex-1 flex-col text-left"
                          >
                            <span className="truncate text-[12.5px] font-medium text-[--color-text-primary]">
                              {t.name}
                            </span>
                            <span className="font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-tertiary]">
                              {t.is_builtin ? "built-in" : "uploaded"}
                            </span>
                          </button>
                          {!t.is_builtin ? (
                            <button
                              type="button"
                              aria-label={`Delete template ${t.name}`}
                              onClick={() => handleDelete(t.id)}
                              className="rounded p-1 text-[--color-feedback-danger] hover:bg-[--color-surface-hover]"
                            >
                              <Trash size={12} />
                            </button>
                          ) : null}
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section
              className="border-b border-[--color-border-subtle] px-[22px] py-[18px]"
              data-testid="er-v3-instructions-picker"
            >
              <div className="mb-[10px] flex items-center justify-between">
                <SectionHeader label="Instructions" />
                <button
                  type="button"
                  onClick={onUploadInstructionsClick}
                  data-testid="er-v3-instructions-upload-trigger"
                  className="inline-flex items-center gap-[6px] rounded-md border border-dashed border-[--color-border-strong] bg-transparent px-[10px] py-[3px] font-mono text-[10px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-solid hover:border-[--color-feedback-success] hover:text-[--color-feedback-success]"
                >
                  <Upload size={11} strokeWidth={2} />
                  Upload
                </button>
              </div>
              <p className="mb-[10px] text-[12px] leading-[1.5] text-[--color-text-secondary]">
                Instructions are your standing guidance for how the analyst
                should work — what to focus on, the angle to take, the tone to
                use — like a brief you'd hand a human analyst. Optional, but
                required when no template is selected so the analyst knows what
                to produce.
              </p>
              <button
                type="button"
                onClick={() => pickInstructions(null)}
                data-testid="er-v3-instructions-option-none"
                className={[
                  "mb-[6px] flex w-full flex-col rounded-md border px-3 py-2 text-left",
                  instructionsId === null
                    ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
                    : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
                ].join(" ")}
              >
                <span className="text-[12.5px] font-medium text-[--color-text-primary]">
                  None
                </span>
              </button>
              {instructions === null ? (
                <p className="text-[12px] text-[--color-text-tertiary]">
                  Loading instructions…
                </p>
              ) : instructionsError ? (
                <p className="text-[12px] text-[--color-feedback-danger]">
                  {instructionsError}
                </p>
              ) : instructions.length === 0 ? (
                <p className="text-[12px] text-[--color-text-tertiary]">
                  No instruction profiles yet.
                </p>
              ) : (
                <ul className="flex flex-col gap-[4px]">
                  {instructions.map((i) => {
                    const active = instructionsId === i.id;
                    return (
                      <li key={i.id}>
                        <div
                          className={[
                            "flex items-center gap-2 rounded-md border px-3 py-2",
                            active
                              ? "border-[--color-accent-primary] bg-[rgba(212,255,0,0.06)]"
                              : "border-[--color-border-subtle] bg-[--color-bg-base] hover:border-[--color-border-strong]",
                          ].join(" ")}
                        >
                          <button
                            type="button"
                            onClick={() => pickInstructions(i)}
                            data-testid={`er-v3-instructions-option-${i.id}`}
                            className="flex min-w-0 flex-1 flex-col text-left"
                          >
                            <span className="truncate text-[12.5px] font-medium text-[--color-text-primary]">
                              {i.name}
                            </span>
                          </button>
                          <button
                            type="button"
                            aria-label={`Delete instructions ${i.name}`}
                            onClick={() => handleDeleteInstructions(i.id)}
                            className="rounded p-1 text-[--color-feedback-danger] hover:bg-[--color-surface-hover]"
                          >
                            <Trash size={12} />
                          </button>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              {freeformNeedsInstructions ? (
                <p
                  role="alert"
                  data-testid="er-v3-freeform-needs-instructions"
                  className="mt-[10px] text-[12px] text-[--color-feedback-danger]"
                >
                  Select an instruction profile — a run with no template
                  needs one to define the report.
                </p>
              ) : null}
            </section>
          </div>

          <div className="flex justify-end gap-2 rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[14px]">
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-4 font-display text-[13.5px] font-medium text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={save}
              disabled={freeformNeedsInstructions}
              data-testid="er-v3-settings-save"
              className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
            >
              Save
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
