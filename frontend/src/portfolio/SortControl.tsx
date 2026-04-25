import { SORT_LABELS, type SortKey } from "./useSortedHoldings";

export interface SortControlProps {
  readonly value: SortKey;
  readonly onChange: (k: SortKey) => void;
}

const ORDER: readonly SortKey[] = ["alpha-asc", "alpha-desc", "price-desc", "price-asc"];

export function SortControl({ value, onChange }: SortControlProps): JSX.Element {
  return (
    <label className="inline-flex items-center gap-2 text-xs text-[--color-text-tertiary]">
      <span>Sort</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as SortKey)}
        data-testid="sort-control"
        className="text-sm bg-transparent border border-[--color-border-subtle] rounded-[--radius-sm] px-2 py-1 text-[--color-text-primary]"
      >
        {ORDER.map((k) => (
          <option key={k} value={k}>
            {SORT_LABELS[k]}
          </option>
        ))}
      </select>
    </label>
  );
}
