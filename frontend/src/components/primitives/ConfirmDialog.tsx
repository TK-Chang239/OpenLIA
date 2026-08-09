import { useEffect, useRef } from "react";
import type { JSX } from "react";
import { useTranslation } from "react-i18next";

interface Props {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Lightweight confirm dialog primitive — focus-trapped, role="alertdialog",
 * Esc cancels, Enter confirms. Backdrop fades and the panel eases up on open
 * (motion-safe); the backdrop blocks interaction with content behind it.
 */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel,
  destructive = false,
  onConfirm,
  onCancel,
}: Props): JSX.Element | null {
  const { t } = useTranslation();
  const resolvedConfirm = confirmLabel ?? t("common.confirm");
  const resolvedCancel = cancelLabel ?? t("common.cancel");
  const cancelRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    cancelRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        onConfirm();
        return;
      }
      if (e.key === "Tab") {
        const dlg = dialogRef.current;
        if (!dlg) return;
        const focusables = dlg.querySelectorAll<HTMLElement>(
          'button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        const active = document.activeElement;
        if (e.shiftKey && active === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && active === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [open, onConfirm, onCancel]);

  if (!open) return null;

  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby={description ? "confirm-dialog-description" : undefined}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4 motion-safe:animate-overlay-in"
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        className="w-full max-w-sm rounded-lg border border-[--color-border-subtle] bg-[--color-bg-elevated] p-5 shadow-xl motion-safe:animate-dialog-in"
      >
        <h2
          id="confirm-dialog-title"
          className="text-base font-semibold text-[--color-text-primary]"
        >
          {title}
        </h2>
        {description ? (
          <p
            id="confirm-dialog-description"
            className="mt-2 text-sm text-[--color-text-secondary]"
          >
            {description}
          </p>
        ) : null}
        <div className="mt-5 flex justify-end gap-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="rounded-md border border-[--color-border-subtle] px-3 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
          >
            {resolvedCancel}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={onConfirm}
            className={`rounded-md px-3 py-1.5 text-sm text-white ${destructive ? "bg-[--color-feedback-error] hover:opacity-90" : "bg-[--color-accent-primary] hover:opacity-90"}`}
          >
            {resolvedConfirm}
          </button>
        </div>
      </div>
    </div>
  );
}
