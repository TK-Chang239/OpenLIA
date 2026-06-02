/**
 * MbTemplateUploadModal — upload a user-defined Morning Briefing template.
 *
 * Accepts .md and .docx. Markdown is read client-side and handed to the
 * parent as ``{ name, markdown }``; .docx is handed back as ``{ name, file
 * }`` for the server's multipart ingest. The parent persists via
 * ``useMbTemplates().create`` / ``.upload``.
 */
import { Upload, X } from "lucide-react";
import { type ChangeEvent, type JSX, useState } from "react";
import { useTranslation } from "react-i18next";

type UploadKind = "markdown" | "docx";

function detectKind(filename: string): UploadKind | null {
  const lower = filename.toLowerCase();
  if (
    lower.endsWith(".md") ||
    lower.endsWith(".markdown") ||
    lower.endsWith(".txt")
  ) {
    return "markdown";
  }
  if (lower.endsWith(".docx")) return "docx";
  return null;
}

function nameFromFile(filename: string, fallback: string): string {
  return filename.replace(/\.(md|markdown|txt|docx)$/i, "") || fallback;
}

function sectionCount(md: string): number {
  let n = 0;
  for (const line of md.split("\n")) {
    if (/^#{1,2}\s+\S/.test(line)) n += 1;
  }
  return n;
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Markdown picked client-side — parent persists via create(). */
  onUploadMarkdown: (name: string, markdown: string) => Promise<void>;
  /** Document file — parent persists via upload() (server ingest). */
  onUploadFile: (name: string, file: File) => Promise<void>;
}

export function MbTemplateUploadModal({
  open,
  onClose,
  onUploadMarkdown,
  onUploadFile,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const fallbackName = t("morning_briefing.template_upload.untitled");
  const [name, setName] = useState(fallbackName);
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const reset = () => {
    setName(fallbackName);
    setMarkdown(null);
    setFile(null);
    setFilename(null);
    setError(null);
    setBusy(false);
  };

  const handleClose = () => {
    if (busy) return;
    reset();
    onClose();
  };

  async function handleFile(e: ChangeEvent<HTMLInputElement>): Promise<void> {
    const picked = e.target.files?.[0];
    if (!picked) return;
    setError(null);
    setFilename(picked.name);
    setName(nameFromFile(picked.name, fallbackName));
    const kind = detectKind(picked.name);
    try {
      if (kind === "markdown") {
        const text = await picked.text();
        setMarkdown(text);
        setFile(null);
      } else if (kind === "docx") {
        setFile(picked);
        setMarkdown(null);
      } else {
        setError(
          t("morning_briefing.template_upload.unsupported", {
            filename: picked.name,
          }),
        );
        setMarkdown(null);
        setFile(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setMarkdown(null);
      setFile(null);
    }
  }

  const save = async () => {
    if (!name.trim() || (markdown === null && file === null)) return;
    setBusy(true);
    setError(null);
    try {
      if (markdown !== null) {
        await onUploadMarkdown(name.trim(), markdown);
      } else if (file !== null) {
        await onUploadFile(name.trim(), file);
      }
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  const canSave =
    Boolean(name.trim()) && (markdown !== null || file !== null) && !busy;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mb-template-upload-title"
      data-testid="mb-template-upload-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={handleClose}
    >
      <div
        className="flex w-full max-w-[480px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[16px]">
          <h2
            id="mb-template-upload-title"
            className="m-0 text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            {t("morning_briefing.template_upload.title")}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label={t("morning_briefing.template_upload.close_aria")}
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="flex flex-col gap-[14px] px-[22px] py-[16px]">
          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("morning_briefing.template_upload.file_label")}
            </span>
            <div className="flex items-center gap-2">
              <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 text-[13px] text-[--color-text-secondary] hover:border-[--color-border-strong]">
                <Upload size={12} strokeWidth={2} />
                {filename ?? t("morning_briefing.template_upload.choose_file")}
                <input
                  type="file"
                  accept=".md,.markdown,.txt,.docx"
                  onChange={handleFile}
                  data-testid="mb-template-upload-file-input"
                  className="hidden"
                  disabled={busy}
                />
              </label>
            </div>
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("morning_briefing.template_upload.name_label")}
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={256}
              data-testid="mb-template-upload-name"
              className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            />
          </label>

          {markdown ? (
            <div
              data-testid="mb-template-upload-preview"
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-[11.5px] text-[--color-text-secondary]"
            >
              {t("morning_briefing.template_upload.preview", {
                count: sectionCount(markdown),
              })}
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              data-testid="mb-template-upload-error"
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
            {t("morning_briefing.template_upload.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={!canSave}
            data-testid="mb-template-upload-save"
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy
              ? t("morning_briefing.template_upload.saving")
              : t("morning_briefing.template_upload.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
