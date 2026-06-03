import { CalendarClock, FileText, Library } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Props {
  onRunNow: () => void;
  onOpenLibrary: () => void;
}

export function MbEmptyPage({ onRunNow, onOpenLibrary }: Props) {
  const { t } = useTranslation();
  return (
    <div
      data-testid="mb-empty-page"
      className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
    >
      <div
        aria-hidden="true"
        className="mb-5 flex h-12 w-12 items-center justify-center rounded-[14px] bg-[--color-accent-primary] text-[--color-accent-on] shadow-[0_0_24px_rgba(212,255,0,0.35)]"
      >
        <CalendarClock size={24} strokeWidth={1.6} />
      </div>
      <h2 className="text-[20px] font-semibold text-[--color-text-primary] m-0 mb-2">
        {t("morning_briefing.empty_title")}
      </h2>
      <p className="text-[14px] text-[--color-text-secondary] max-w-[480px] m-0 mb-5 leading-[1.5]">
        {t("morning_briefing.empty_sub")}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRunNow}
          data-testid="mb-empty-run-now"
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
        >
          <FileText size={14} /> {t("morning_briefing.run_now")}
        </button>
        <button
          type="button"
          onClick={onOpenLibrary}
          data-testid="mb-empty-open-library"
          className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md border border-[--color-border-subtle] bg-transparent text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-surface-hover] hover:border-[--color-border-strong] text-[13px] font-medium transition-colors duration-[--duration-normal]"
        >
          <Library size={14} /> {t("morning_briefing.open_library")}
        </button>
      </div>
    </div>
  );
}
