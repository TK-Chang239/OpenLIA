import { Briefcase } from "lucide-react";
import { useTranslation } from "react-i18next";

interface Props {
  onOpenCoverage: () => void;
}

export function EuEmptyPage({ onOpenCoverage }: Props) {
  const { t } = useTranslation();
  return (
    <div
      data-testid="eu-empty-page"
      className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
    >
      <h2 className="text-[20px] font-semibold text-[--color-text-primary] m-0 mb-2">
        {t("earnings.feed.empty_title")}
      </h2>
      <p className="text-[14px] text-[--color-text-secondary] max-w-[480px] m-0 mb-5 leading-[1.5]">
        {t("earnings.feed.empty_sub")}
      </p>
      <button
        type="button"
        onClick={onOpenCoverage}
        className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
      >
        <Briefcase size={14} /> {t("earnings.feed.open_coverage")}
      </button>
    </div>
  );
}
