import * as Dialog from "@radix-ui/react-dialog";
import { useTranslation } from "react-i18next";

export interface DeleteReportDialogProps {
  open: boolean;
  reportTitle: string;
  onCancel: () => void;
  onConfirm: () => void | Promise<void>;
}

/**
 * Destructive-action dialog for permanently deleting a saved report after
 * its 7-day grace window has elapsed. Used by all four card surfaces
 * (Repository row, Equity Research card, Earnings Update list, Morning
 * Briefing archive). The chat-history artifact card stays visible after
 * delete, replaced with a "no longer available" tombstone — the copy
 * mentions this so the user is not surprised later.
 */
export function DeleteReportDialog({
  open,
  reportTitle,
  onCancel,
  onConfirm,
}: DeleteReportDialogProps): JSX.Element {
  const { t } = useTranslation();
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
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] max-w-[440px] w-full p-6"
          data-testid="delete-report-dialog"
        >
          <Dialog.Title className="text-base font-semibold text-[--color-text-primary]">
            {t("report.delete_this_report_title")}
          </Dialog.Title>
          <Dialog.Description className="mt-3 text-sm text-[--color-text-secondary]">
            <span className="font-medium text-[--color-text-primary]">"{reportTitle}"</span>{" "}
            {t("report.delete_description_prefix")}
          </Dialog.Description>
          <div className="mt-6 flex justify-end gap-2">
            <button
              type="button"
              onClick={onCancel}
              className="h-9 px-4 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary]"
            >
              {t("common.cancel")}
            </button>
            <button
              type="button"
              onClick={() => {
                void onConfirm();
              }}
              className="h-9 px-4 rounded-[--radius-md] bg-[--color-feedback-error] text-white text-sm font-medium hover:opacity-90"
            >
              {t("common.delete")}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
