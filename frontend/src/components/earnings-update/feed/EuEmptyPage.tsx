import { Briefcase } from "lucide-react";

interface Props {
  onOpenCoverage: () => void;
}

export function EuEmptyPage({ onOpenCoverage }: Props) {
  return (
    <div
      data-testid="eu-empty-page"
      className="flex flex-col items-center justify-center text-center py-20 px-6 border border-dashed border-[--color-border-subtle] rounded-[12px] bg-[--color-bg-elevated]"
    >
      <h2 className="text-[20px] font-semibold text-[--color-text-primary] m-0 mb-2">
        No earnings reports yet
      </h2>
      <p className="text-[14px] text-[--color-text-secondary] max-w-[480px] m-0 mb-5 leading-[1.5]">
        Add tickers to your watchlist and LIA will auto-generate reports as
        each company releases earnings.
      </p>
      <button
        type="button"
        onClick={onOpenCoverage}
        className="inline-flex items-center gap-1.5 h-9 px-4 rounded-md bg-[--color-accent-primary] text-[--color-accent-on] text-[13px] font-medium hover:bg-[--color-accent-hover] transition-colors duration-[--duration-normal]"
      >
        <Briefcase size={14} /> Open Coverage
      </button>
    </div>
  );
}
