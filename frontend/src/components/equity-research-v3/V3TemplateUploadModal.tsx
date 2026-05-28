/**
 * V3TemplateUploadModal — upload a user-defined v3 template.
 *
 * Accepts .md and .docx; docx → markdown via the existing
 * ``/api/report-templates/ingest`` endpoint (engine-agnostic), then
 * POSTs the markdown to v3's ``/templates`` endpoint. JSON upload is
 * intentionally out of scope for PR3 — the markdown format is the
 * canonical authoring surface and JSON support can land later if
 * users want hand-written specs.
 *
 * UX: file picker -> auto-fill name from filename -> Save. Errors
 * (unsupported file type, parse failure, empty sections) render
 * inline above the footer.
 */
import { Upload, X } from "lucide-react";
import { type ChangeEvent, type JSX, useState } from "react";

import { ingestTemplateDocument } from "../../api/report-templates";
import {
  type V3TemplateSummary,
  uploadV3Template,
} from "../../api/equity-research-v3";

type UploadKind = "markdown" | "docx";

function detectKind(filename: string): UploadKind | null {
  const lower = filename.toLowerCase();
  if (lower.endsWith(".md") || lower.endsWith(".markdown") || lower.endsWith(".txt")) {
    return "markdown";
  }
  if (lower.endsWith(".docx")) return "docx";
  return null;
}

function nameFromFile(filename: string): string {
  return filename.replace(/\.(md|markdown|txt|docx)$/i, "") || "Untitled template";
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Fired after a successful save. Parent uses the new template id
   *  to switch the page's active template selection. */
  onSaved: (template: V3TemplateSummary) => void;
}

export function V3TemplateUploadModal({
  open,
  onClose,
  onSaved,
}: Props): JSX.Element | null {
  const [name, setName] = useState("Untitled template");
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [docxBlob, setDocxBlob] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const reset = () => {
    setName("Untitled template");
    setMarkdown(null);
    setFilename(null);
    setDocxBlob(null);
    setError(null);
    setBusy(false);
  };

  const handleClose = () => {
    if (busy) return;
    reset();
    onClose();
  };

  async function handleFile(e: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setFilename(file.name);
    setName(nameFromFile(file.name));
    const kind = detectKind(file.name);
    try {
      if (kind === "markdown") {
        const text = await file.text();
        setMarkdown(text);
        setDocxBlob(null);
      } else if (kind === "docx") {
        // Ingest via v2.3's shared endpoint (mammoth conversion) —
        // returns markdown ready for our v3 parser.
        const { markdown: md } = await ingestTemplateDocument(file);
        setMarkdown(md);
        // Also stash the original blob as base64 so the server keeps
        // the source artifact for future re-parse / edit flows.
        const arr = await file.arrayBuffer();
        setDocxBlob(arrayBufferToBase64(arr));
      } else {
        setError(`Unsupported file type: ${file.name}. Use .md or .docx.`);
        setMarkdown(null);
        setDocxBlob(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMarkdown(null);
      setDocxBlob(null);
    }
  }

  const save = async () => {
    if (!markdown || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const created = await uploadV3Template({
        name: name.trim(),
        markdown,
        source_doc_blob: docxBlob,
        source_doc_mime: docxBlob
          ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          : null,
      });
      reset();
      onSaved(created);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  const canSave = Boolean(markdown && name.trim()) && !busy;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="v3-template-upload-title"
      data-testid="v3-template-upload-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={handleClose}
    >
      <div
        className="flex w-full max-w-[480px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[16px]">
          <h2
            id="v3-template-upload-title"
            className="m-0 text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            Upload v3 template
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close"
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="flex flex-col gap-[14px] px-[22px] py-[16px]">
          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              File (.md or .docx)
            </span>
            <div className="flex items-center gap-2">
              <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 text-[13px] text-[--color-text-secondary] hover:border-[--color-border-strong]">
                <Upload size={12} strokeWidth={2} />
                {filename ?? "Choose file"}
                <input
                  type="file"
                  accept=".md,.markdown,.txt,.docx"
                  onChange={handleFile}
                  data-testid="v3-template-upload-file-input"
                  className="hidden"
                  disabled={busy}
                />
              </label>
            </div>
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              Display name
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={256}
              data-testid="v3-template-upload-name"
              className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            />
          </label>

          {markdown ? (
            <div
              data-testid="v3-template-upload-preview"
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-[11.5px] text-[--color-text-secondary]"
            >
              Parsed {sectionCount(markdown)} section(s). The server will
              compile and validate on save.
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              data-testid="v3-template-upload-error"
              className="rounded-md border border-[--color-feedback-danger] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-danger]"
            >
              {error}
            </div>
          ) : null}
        </div>

        <div className="flex justify-end gap-2 rounded-b-[14px] border-t border-[--color-border-subtle] bg-[--color-bg-base] px-[22px] py-[12px]">
          <button
            type="button"
            onClick={handleClose}
            disabled={busy}
            className="inline-flex h-9 items-center rounded-md border border-[--color-border-subtle] bg-transparent px-4 font-display text-[13px] font-medium text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={save}
            disabled={!canSave}
            data-testid="v3-template-upload-save"
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}

// Local preview helper — counts H1/H2 markdown headings so the user
// gets a "X section(s) found" hint before committing. Server is the
// authoritative parser; this is purely informational.
function sectionCount(md: string): number {
  const lines = md.split("\n");
  let n = 0;
  for (const line of lines) {
    if (/^#{1,2}\s+\S/.test(line)) n += 1;
  }
  return n;
}

function arrayBufferToBase64(buf: ArrayBuffer): string {
  let bin = "";
  const bytes = new Uint8Array(buf);
  for (let i = 0; i < bytes.byteLength; i += 1) {
    bin += String.fromCharCode(bytes[i]);
  }
  return btoa(bin);
}
