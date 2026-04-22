import type { ReactNode } from "react";

export function WizardFooter({
  onBack,
  onNext,
  nextLabel = "Next",
  nextDisabled,
  loading,
  rightSlot,
}: {
  onBack?: () => void;
  onNext?: () => void;
  nextLabel?: string;
  nextDisabled?: boolean;
  loading?: boolean;
  rightSlot?: ReactNode;
}) {
  return (
    <div className="h-16 flex items-center justify-between px-6 border-t border-[--color-border-subtle]">
      {onBack ? (
        <button
          type="button"
          onClick={onBack}
          className="h-10 px-4 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          Back
        </button>
      ) : (
        <span />
      )}
      <div className="flex items-center gap-3">
        {rightSlot}
        {onNext ? (
          <button
            type="button"
            onClick={onNext}
            disabled={nextDisabled || loading}
            className={
              nextDisabled || loading
                ? "h-10 px-5 rounded-[--radius-md] text-sm font-medium bg-[--color-surface-active] text-[--color-text-tertiary] cursor-not-allowed"
                : "h-10 px-5 rounded-[--radius-md] text-sm font-medium bg-[--color-accent-primary] text-white hover:bg-[--color-accent-hover]"
            }
          >
            {loading ? "Saving…" : nextLabel}
          </button>
        ) : null}
      </div>
    </div>
  );
}
