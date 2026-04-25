import * as Dialog from "@radix-ui/react-dialog";

export interface RemoveConfirmDialogProps {
  open: boolean;
  filename: string;
  onCancel: () => void;
  onConfirm: () => void;
}

export function RemoveConfirmDialog({
  open,
  filename,
  onCancel,
  onConfirm,
}: RemoveConfirmDialogProps): JSX.Element {
  return (
    <Dialog.Root
      open={open}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/40 z-40" />
        <Dialog.Content
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] max-w-[400px] w-full p-6"
          data-testid="remove-confirm-dialog"
        >
          <Dialog.Title className="text-base font-semibold text-[--color-text-primary]">
            Remove from Repository?
          </Dialog.Title>
          <Dialog.Description className="mt-3 text-sm text-[--color-text-secondary]">
            <span className="font-medium text-[--color-text-primary]">"{filename}"</span> will be
            removed from your Repository.
          </Dialog.Description>
          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="h-9 px-4 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={onConfirm}
              className="h-9 px-4 rounded-[--radius-md] bg-[--color-feedback-error] text-white text-sm font-medium hover:opacity-90"
            >
              Remove
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
