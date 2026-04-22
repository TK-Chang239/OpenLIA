import React from 'react';

interface Props {
  open: boolean;
  onConfirmDiscard: () => void;
  onCancel: () => void;
}

export function UnsavedChangesModal({ open, onConfirmDiscard, onCancel }: Props): JSX.Element | null {
  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="unsaved-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
    >
      <div className="w-full max-w-md rounded-xl bg-bg-elevated p-6 shadow-xl">
        <h2 id="unsaved-title" className="text-lg font-semibold text-text-primary">
          Discard unsaved changes?
        </h2>
        <p className="mt-2 text-sm text-text-secondary">
          You have unsaved changes in this section. Leaving will lose them.
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="rounded-md border border-border-subtle px-3 py-1.5 text-sm text-text-primary hover:bg-surface-hover"
          >
            Stay
          </button>
          <button
            type="button"
            onClick={onConfirmDiscard}
            className="rounded-md bg-feedback-error px-3 py-1.5 text-sm font-medium text-white hover:bg-feedback-error/90"
          >
            Discard
          </button>
        </div>
      </div>
    </div>
  );
}
