/**
 * MbInstructionsUploadModal — upload a saved instruction profile for
 * Morning Briefing.
 *
 * The raw document is handed back to the parent which persists it via
 * ``useMbInstructions().upload`` (multipart; the server extracts plain
 * text). There is no client-side ingest step and no section preview — an
 * instruction profile is free-form methodology, not a section skeleton.
 */
import { Upload, X } from "lucide-react";
import { type ChangeEvent, type JSX, useState } from "react";
import { useTranslation } from "react-i18next";

const ACCEPT = ".pdf,.docx,.md,.markdown,.txt";

function isSupported(filename: string): boolean {
  return /\.(pdf|docx|md|markdown|txt)$/i.test(filename);
}

function nameFromFile(filename: string): string {
  return filename.replace(/\.(pdf|docx|md|markdown|txt)$/i, "");
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** Persisted by the parent via useMbInstructions().upload. */
  onUpload: (name: string, file: File) => Promise<void>;
}

export function MbInstructionsUploadModal({
  open,
  onClose,
  onUpload,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const fallbackName = t("morning_briefing.instructions_upload.untitled");
  const [name, setName] = useState(fallbackName);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!open) return null;

  const reset = () => {
    setName(fallbackName);
    setFile(null);
    setError(null);
    setBusy(false);
  };

  const handleClose = () => {
    if (busy) return;
    reset();
    onClose();
  };

  function handleFile(e: ChangeEvent<HTMLInputElement>): void {
    const picked = e.target.files?.[0];
    if (!picked) return;
    setError(null);
    if (!isSupported(picked.name)) {
      setError(
        t("morning_briefing.instructions_upload.unsupported", {
          filename: picked.name,
        }),
      );
      setFile(null);
      return;
    }
    setFile(picked);
    setName(nameFromFile(picked.name) || fallbackName);
  }

  const save = async () => {
    if (!file || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await onUpload(name.trim(), file);
      reset();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  };

  const canSave = Boolean(file && name.trim()) && !busy;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mb-instructions-upload-title"
      data-testid="mb-instructions-upload-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={handleClose}
    >
      <div
        className="flex w-full max-w-[480px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[16px]">
          <h2
            id="mb-instructions-upload-title"
            className="m-0 text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            {t("morning_briefing.instructions_upload.title")}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label={t("morning_briefing.instructions_upload.close_aria")}
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="flex flex-col gap-[14px] px-[22px] py-[16px]">
          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("morning_briefing.instructions_upload.file_label")}
            </span>
            <div className="flex items-center gap-2">
              <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 text-[13px] text-[--color-text-secondary] hover:border-[--color-border-strong]">
                <Upload size={12} strokeWidth={2} />
                {file?.name ??
                  t("morning_briefing.instructions_upload.choose_file")}
                <input
                  type="file"
                  accept={ACCEPT}
                  onChange={handleFile}
                  data-testid="mb-instructions-upload-file-input"
                  className="hidden"
                  disabled={busy}
                />
              </label>
            </div>
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("morning_briefing.instructions_upload.name_label")}
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={256}
              data-testid="mb-instructions-upload-name"
              className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            />
          </label>

          {file ? (
            <div
              data-testid="mb-instructions-upload-preview"
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-[11.5px] text-[--color-text-secondary]"
            >
              {t("morning_briefing.instructions_upload.preview")}
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              data-testid="mb-instructions-upload-error"
              className="rounded-md border border-[--color-feedback-error] bg-[rgba(220,80,80,0.08)] px-3 py-2 text-[12px] text-[--color-feedback-error]"
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
            {t("morning_briefing.instructions_upload.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={!canSave}
            data-testid="mb-instructions-upload-save"
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy
              ? t("morning_briefing.instructions_upload.saving")
              : t("morning_briefing.instructions_upload.save")}
          </button>
        </div>
      </div>
    </div>
  );
}
