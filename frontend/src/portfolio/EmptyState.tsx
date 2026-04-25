import { BarChart2 } from "lucide-react";

export function EmptyState(): JSX.Element {
  return (
    <div
      className="flex flex-col items-center justify-center py-16 text-center"
      data-testid="portfolio-empty"
    >
      <BarChart2
        className="text-[--color-text-tertiary] mb-3"
        size={48}
        aria-hidden="true"
      />
      <h2 className="text-lg font-semibold text-[--color-text-primary]">
        Your portfolio is empty
      </h2>
      <p className="mt-1 text-sm text-[--color-text-tertiary]">
        Search above to add tickers
      </p>
    </div>
  );
}
