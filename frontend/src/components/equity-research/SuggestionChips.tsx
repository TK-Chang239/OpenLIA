import { FromPortfolioPicker } from "./FromPortfolioPicker";

const STATIC_TICKERS = ["AAPL", "TSLA", "NVDA", "MSFT"] as const;

interface Props {
  onSelect: (value: string) => void;
}

export function SuggestionChips({ onSelect }: Props) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {STATIC_TICKERS.map((t) => (
        <button
          key={t}
          type="button"
          onClick={() => onSelect(t)}
          className="px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]"
        >
          {t}
        </button>
      ))}
      <FromPortfolioPicker onSelect={onSelect} />
    </div>
  );
}
