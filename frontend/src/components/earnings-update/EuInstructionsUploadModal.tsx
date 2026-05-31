/**
 * EuInstructionsUploadModal — upload a saved instruction profile for
 * Earnings Update v2.
 *
 * Mirrors the v3 instructions upload modal: the raw document is sent
 * straight to v2's multipart ``/instructions`` endpoint and the server
 * extracts plain text (pdf / docx / md / txt all supported). There is
 * no client-side ingest step and no section preview — an instruction
 * profile is free-form methodology, not a section skeleton.
 *
 * UX: file picker -> auto-fill name from filename -> Save. Errors
 * (unsupported file type, empty extraction) render inline above the
 * footer.
 */
import { Upload, X } from "lucide-react";
import { type ChangeEvent, type JSX, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  type EuInstructionsSummary,
  uploadEuInstructions,
} from "../../api/earnings-update";

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
  /** Fired after a successful save. Parent uses the new profile to
   *  switch the active instructions selection. */
  onSaved: (profile: EuInstructionsSummary) => void;
}

export function EuInstructionsUploadModal({
  open,
  onClose,
  onSaved,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const fallbackName = t("earnings.settings_modal.instructions_untitled");
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
        t("earnings.settings_modal.instructions_upload_unsupported", {
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
      const created = await uploadEuInstructions(name.trim(), file);
      reset();
      onSaved(created);
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
      aria-labelledby="eu-instructions-upload-title"
      data-testid="eu-instructions-upload-modal"
      className="fixed inset-0 z-[60] flex items-center justify-center bg-[rgba(13,13,11,0.55)]"
      onClick={handleClose}
    >
      <div
        className="flex w-full max-w-[480px] flex-col rounded-[14px] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-[0_16px_40px_rgba(13,13,11,0.18)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center border-b border-[--color-border-subtle] px-[22px] py-[16px]">
          <h2
            id="eu-instructions-upload-title"
            className="m-0 text-[14px] font-semibold tracking-[-0.005em] text-[--color-text-primary]"
          >
            {t("earnings.settings_modal.instructions_upload_title")}
          </h2>
          <button
            type="button"
            onClick={handleClose}
            aria-label={t("earnings.settings_modal.instructions_upload_close_aria")}
            className="ml-auto inline-flex h-7 w-7 items-center justify-center rounded-md text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>

        <div className="flex flex-col gap-[14px] px-[22px] py-[16px]">
          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("earnings.settings_modal.instructions_upload_file_label")}
            </span>
            <div className="flex items-center gap-2">
              <label className="inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 text-[13px] text-[--color-text-secondary] hover:border-[--color-border-strong]">
                <Upload size={12} strokeWidth={2} />
                {file?.name ?? t("earnings.settings_modal.instructions_upload_choose_file")}
                <input
                  type="file"
                  accept={ACCEPT}
                  onChange={handleFile}
                  data-testid="eu-instructions-upload-file-input"
                  className="hidden"
                  disabled={busy}
                />
              </label>
            </div>
          </label>

          <label className="flex flex-col gap-[6px]">
            <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[--color-text-tertiary]">
              {t("earnings.settings_modal.instructions_upload_name_label")}
            </span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={256}
              data-testid="eu-instructions-upload-name"
              className="h-9 rounded-md border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-[13px] text-[--color-text-primary] outline-none focus:border-[--color-accent-primary]"
            />
          </label>

          {file ? (
            <div
              data-testid="eu-instructions-upload-preview"
              className="rounded-md border border-[--color-border-subtle] bg-[--color-bg-base] px-3 py-2 text-[11.5px] text-[--color-text-secondary]"
            >
              {t("earnings.settings_modal.instructions_upload_preview")}
            </div>
          ) : null}

          {error ? (
            <div
              role="alert"
              data-testid="eu-instructions-upload-error"
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
            {t("earnings.settings_modal.cancel")}
          </button>
          <button
            type="button"
            onClick={() => void save()}
            disabled={!canSave}
            data-testid="eu-instructions-upload-save"
            className="inline-flex h-9 items-center rounded-md bg-[--color-accent-primary] px-4 font-display text-[13px] font-medium text-[--color-accent-on] hover:bg-[--color-accent-hover] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {busy
              ? t("earnings.settings_modal.v2_saving")
              : t("earnings.settings_modal.v2_save")}
          </button>
        </div>
      </div>
    </div>
  );
}
