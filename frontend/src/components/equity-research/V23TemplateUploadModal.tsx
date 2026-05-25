/**
 * V23TemplateUploadModal — overlay that turns a v2.3 template (pasted
 * markdown OR an uploaded .md / .json / .docx file) into a TemplateSpec
 * and persists it via /api/report-templates.
 *
 * Pipelines per source:
 *   - markdown / .md / .markdown / .txt: text -> POST /v23/parse
 *   - .docx: POST /ingest -> markdown -> POST /v23/parse
 *   - .json: parse client-side -> POST /v23/validate
 *
 * In every case the response shape is the same {template_spec,
 * validation_errors} envelope so the preview + Save paths stay shared.
 * Save hits POST /api/report-templates and fires onSaved with the new
 * row id so the caller can auto-select it in the picker.
 */
import { type JSX, useCallback, useEffect, useRef, useState } from "react";

import {
  ingestTemplateDocument,
  parseMarkdownV23,
  saveReportTemplate,
  type TemplateSpec,
  validateV23TemplateJson,
} from "../../api/report-templates";

export interface V23TemplateUploadModalProps {
  open: boolean;
  onSaved: (templateId: string) => void;
  onClose: () => void;
}

type UploadKind = "markdown" | "json" | "docx";

function detectKind(filename: string): UploadKind | null {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".md") || lower.endsWith(".markdown") || lower.endsWith(".txt")) {
    return "markdown";
  }
  if (lower.endsWith(".json")) return "json";
  if (lower.endsWith(".docx")) return "docx";
  return null;
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
  // Original markdown (for md/docx) or stringified JSON (for json) the
  // user supplied — stored so the row's source_markdown field still
  // round-trips a human-readable rendering of the upload.
  const [sourceText, setSourceText] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

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

  // Reset state every time the modal is reopened so prior markdown,
  // parsed preview, and error messages do not bleed into a fresh
  // session. The component stays mounted (returns null when !open),
  // so without this useState's initialisers never re-run.
  useEffect(() => {
    if (!open) return;
    setMarkdown("");
    setName("Untitled template");
    setParsed(null);
    setErrors([]);
    setSubmitError(null);
    setSourceText("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, [open]);

  if (!open) return null;

  function applyEnvelope(
    result: { template_spec: unknown; validation_errors: string[] },
    nextSource: string,
  ): void {
    if (result.validation_errors.length > 0) {
      setParsed(null);
      setErrors(result.validation_errors);
    } else {
      setParsed(result.template_spec as TemplateSpec);
      setErrors([]);
    }
    setSourceText(nextSource);
  }

  async function handleParse() {
    setBusy(true);
    setSubmitError(null);
    try {
      const result = await parseMarkdownV23(markdown, name);
      applyEnvelope(result, markdown);
    } catch (e) {
      setParsed(null);
      setErrors([]);
      setSubmitError(e instanceof Error ? e.message : "failed to parse");
    } finally {
      setBusy(false);
    }
  }

  async function handleFile(file: File): Promise<void> {
    const kind = detectKind(file.name);
    if (kind === null) {
      setSubmitError(
        `Unsupported file type: ${file.name}. Use .md, .json, or .docx.`,
      );
      return;
    }
    setBusy(true);
    setSubmitError(null);
    setParsed(null);
    setErrors([]);
    try {
      if (kind === "markdown") {
        const text = await file.text();
        setMarkdown(text);
        const inferred = (name === "Untitled template" && file.name)
          ? file.name.replace(/\.(md|markdown|txt)$/i, "")
          : name;
        if (inferred !== name) setName(inferred);
        const result = await parseMarkdownV23(text, inferred);
        applyEnvelope(result, text);
      } else if (kind === "docx") {
        const { markdown: md } = await ingestTemplateDocument(file);
        setMarkdown(md);
        const inferred = (name === "Untitled template" && file.name)
          ? file.name.replace(/\.docx$/i, "")
          : name;
        if (inferred !== name) setName(inferred);
        const result = await parseMarkdownV23(md, inferred);
        applyEnvelope(result, md);
      } else {
        // JSON: parse client-side so we can surface JSON syntax errors
        // before the round-trip; then validate against the engine
        // schema server-side.
        const text = await file.text();
        let spec: Record<string, unknown>;
        try {
          spec = JSON.parse(text) as Record<string, unknown>;
        } catch (e) {
          setSubmitError(
            `Invalid JSON in ${file.name}: ${e instanceof Error ? e.message : String(e)}`,
          );
          return;
        }
        const inferred =
          (name === "Untitled template" && typeof spec.name === "string"
            ? spec.name
            : name === "Untitled template" && file.name
              ? file.name.replace(/\.json$/i, "")
              : name);
        if (inferred !== name) setName(inferred);
        const result = await validateV23TemplateJson(spec);
        applyEnvelope(result, text);
      }
    } catch (e) {
      setSubmitError(e instanceof Error ? e.message : "failed to read file");
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
        source_markdown: sourceText || markdown || null,
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
            upload · parse · save
          </span>
        </header>
        <p className="text-[12.5px] text-[--color-text-secondary]">
          Upload a .md, .json, or .docx template — or paste markdown
          directly. Parse converts it into a v2.3 TemplateSpec; Save
          persists it and selects it for the next run.
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
            Upload file (.md · .json · .docx)
          </span>
          <input
            ref={fileInputRef}
            type="file"
            accept=".md,.markdown,.txt,.json,.docx,text/markdown,text/plain,application/json,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleFile(file);
            }}
            disabled={busy}
            data-testid="er-v2-3-template-upload-file"
            className="text-[12px] text-[--color-text-primary] file:mr-3 file:rounded-md file:border-0 file:bg-[--color-bg-base] file:px-3 file:py-[6px] file:font-mono file:text-[11px] file:uppercase file:tracking-[0.08em] file:text-[--color-text-secondary] hover:file:bg-[--color-surface-hover] hover:file:text-[--color-text-primary]"
          />
        </label>

        <label className="flex flex-col gap-[4px]">
          <span className="text-[12px] text-[--color-text-primary]">
            Or paste markdown
          </span>
          <textarea
            aria-label="Markdown"
            rows={10}
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
