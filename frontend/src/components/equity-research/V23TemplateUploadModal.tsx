/**
 * V23TemplateUploadModal — overlay that converts a pasted markdown
 * template into a v2.3 TemplateSpec and persists it to the
 * /api/report-templates collection.
 *
 * Flow: user pastes markdown -> Parse hits POST /v23/parse -> preview
 * lists the parsed sections -> Save hits POST /api/report-templates ->
 * onSaved fires with the new row id so the caller can auto-select it
 * in the FrameworkTemplatePicker.
 *
 * Validation errors come back inline from the parse endpoint as a list
 * of strings and render below the parse button (the spec is suppressed
 * in that case so Save stays disabled).
 */
import { type JSX, useCallback, useEffect, useState } from "react";

import {
  parseMarkdownV23,
  saveReportTemplate,
  type TemplateSpec,
} from "../../api/report-templates";

export interface V23TemplateUploadModalProps {
  open: boolean;
  onSaved: (templateId: string) => void;
  onClose: () => void;
}

export function V23TemplateUploadModal({
  open,
  onSaved,
  onClose,
}: V23TemplateUploadModalProps): JSX.Element | null {
  const [markdown, setMarkdown] = useState("");
  const [name, setName] = useState("Untitled template");
  const [parsed, setParsed] = useState<TemplateSpec | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const dismiss = useCallback(() => {
    if (busy) return;
    onClose();
  }, [busy, onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") dismiss();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, dismiss]);

  if (!open) return null;

  async function handleParse() {
    setBusy(true);
    setSubmitError(null);
    try {
      const result = await parseMarkdownV23(markdown, name);
      if (result.validation_errors.length > 0) {
        setParsed(null);
        setErrors(result.validation_errors);
      } else {
        setParsed(result.template_spec as TemplateSpec);
        setErrors([]);
      }
    } catch (e) {
      setParsed(null);
      setErrors([]);
      setSubmitError(e instanceof Error ? e.message : "failed to parse");
    } finally {
      setBusy(false);
    }
  }

  async function handleSave() {
    if (!parsed) return;
    setBusy(true);
    setSubmitError(null);
    try {
      const saved = await saveReportTemplate({
        name,
        template_spec: parsed,
        source_markdown: markdown,
      });
      onSaved(saved.id);
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "failed to save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="er-v2-3-template-upload-title"
      data-testid="er-v2-3-template-upload-modal"
      className="fixed inset-0 z-50 flex items-center justify-center"
    >
      <div
        data-testid="er-v2-3-template-upload-backdrop"
        className="absolute inset-0 bg-black/40"
        onClick={dismiss}
      />
      <div className="relative z-10 mx-4 flex w-full max-w-[640px] flex-col gap-3 rounded-lg border border-[--color-border-subtle] bg-[--color-bg-elevated] px-5 py-4 shadow-lg">
        <header className="flex items-baseline justify-between gap-3">
          <h2
            id="er-v2-3-template-upload-title"
            className="font-display text-[15.5px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            Upload v2.3 template
          </h2>
          <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-[--color-text-tertiary]">
            paste markdown · parse · save
          </span>
        </header>
        <p className="text-[12.5px] text-[--color-text-secondary]">
          Paste a markdown-shaped report outline. Parse converts it into a
          v2.3 TemplateSpec; Save persists it and selects it for the next run.
        </p>

        <label className="flex flex-col gap-[4px]">
          <span className="text-[12px] text-[--color-text-primary]">
            Template name
          </span>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            data-testid="er-v2-3-template-upload-name"
            className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[12px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
          />
        </label>

        <label className="flex flex-col gap-[4px]">
          <span className="text-[12px] text-[--color-text-primary]">
            Markdown
          </span>
          <textarea
            aria-label="Markdown"
            rows={12}
            value={markdown}
            onChange={(e) => setMarkdown(e.target.value)}
            data-testid="er-v2-3-template-upload-markdown"
            className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 font-mono text-[12px] text-[--color-text-primary] outline-none focus:border-[--color-feedback-success]"
          />
        </label>

        <footer className="mt-1 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={dismiss}
            disabled={busy}
            data-testid="er-v2-3-template-upload-cancel"
            className="inline-flex h-8 items-center rounded-md px-3 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:cursor-not-allowed disabled:opacity-40"
          >
            Cancel
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleParse}
              disabled={busy || !markdown}
              data-testid="er-v2-3-template-upload-parse"
              className="inline-flex h-8 items-center rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 font-mono text-[11px] uppercase tracking-[0.08em] text-[--color-text-secondary] hover:border-[--color-border-strong] hover:text-[--color-text-primary] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy && !parsed ? "Parsing…" : "Parse"}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={busy || !parsed}
              data-testid="er-v2-3-template-upload-save"
              className="inline-flex h-8 items-center rounded-md bg-[--color-accent-primary] px-3 font-display text-[12.5px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {busy && parsed ? "Saving…" : "Save"}
            </button>
          </div>
        </footer>

        {submitError ? (
          <div
            role="alert"
            data-testid="er-v2-3-template-upload-error"
            className="rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
          >
            {submitError}
          </div>
        ) : null}

        {errors.length > 0 ? (
          <ul
            data-testid="er-v2-3-template-upload-errors"
            className="flex flex-col gap-[2px] rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
          >
            {errors.map((err) => (
              <li key={err}>{err}</li>
            ))}
          </ul>
        ) : null}

        {parsed ? (
          <div
            data-testid="er-v2-3-template-upload-preview"
            className="flex flex-col gap-[6px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2"
          >
            <h3 className="font-display text-[13px] font-semibold text-[--color-text-primary]">
              {parsed.name}
            </h3>
            {parsed.shape_description ? (
              <p className="text-[12px] text-[--color-text-secondary]">
                {parsed.shape_description}
              </p>
            ) : null}
            <ol className="ml-4 flex list-decimal flex-col gap-[2px] text-[12px] text-[--color-text-primary]">
              {parsed.sections.map((s) => (
                <li key={s.id}>{s.title}</li>
              ))}
            </ol>
          </div>
        ) : null}
      </div>
    </div>
  );
}
