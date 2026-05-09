import type { JSX } from "react";
import { X } from "lucide-react";
import { departmentLabel } from "../../lib/department-colors";

export interface RepoFilterChipsProps {
  q: string;
  departments: string[];
  generatedFrom: string;
  generatedTo: string;
  savedFrom: string;
  savedTo: string;
  onRemoveSearch: () => void;
  onRemoveDepartment: (slug: string) => void;
  onRemoveGeneratedRange: () => void;
  onRemoveSavedRange: () => void;
  onClearAll: () => void;
}

function formatRange(from: string, to: string): string {
  if (from && to) return `${from} – ${to}`;
  if (from) return `from ${from}`;
  if (to) return `until ${to}`;
  return "";
}

export function RepoFilterChips(props: RepoFilterChipsProps): JSX.Element | null {
  const {
    q,
    departments,
    generatedFrom,
    generatedTo,
    savedFrom,
    savedTo,
    onRemoveSearch,
    onRemoveDepartment,
    onRemoveGeneratedRange,
    onRemoveSavedRange,
    onClearAll,
  } = props;
  const hasFilters =
    q !== "" ||
    departments.length > 0 ||
    generatedFrom !== "" ||
    generatedTo !== "" ||
    savedFrom !== "" ||
    savedTo !== "";

  if (!hasFilters) return null;

  const chip = (key: string, label: string, onRemove: () => void) => (
    <span
      key={key}
      className="inline-flex h-[26px] items-center gap-[6px] whitespace-nowrap rounded-full border border-[rgba(168,204,0,0.45)] bg-[rgba(212,255,0,0.10)] pl-[10px] pr-2 text-[12px] font-medium text-[--color-accent-on-tint]"
      data-testid="filter-chip"
    >
      <span>{label}</span>
      <button
        type="button"
        aria-label={`Remove filter ${label}`}
        onClick={onRemove}
        className="inline-flex h-[14px] w-[14px] items-center justify-center rounded-full opacity-70 transition-[opacity,background-color] hover:bg-[rgba(61,77,0,0.10)] hover:opacity-100"
      >
        <X size={9} strokeWidth={2.4} />
      </button>
    </span>
  );

  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-[--color-border-subtle] px-6 py-[10px]"
      data-testid="filter-chips"
    >
      {q !== "" && chip("q", `Search: "${q}"`, onRemoveSearch)}
      {departments.map((d) =>
        chip(`dept-${d}`, `Department: ${departmentLabel(d)}`, () =>
          onRemoveDepartment(d),
        ),
      )}
      {(generatedFrom || generatedTo) &&
        chip(
          "gen-range",
          `Date Generated: ${formatRange(generatedFrom, generatedTo)}`,
          onRemoveGeneratedRange,
        )}
      {(savedFrom || savedTo) &&
        chip(
          "saved-range",
          `Date Saved: ${formatRange(savedFrom, savedTo)}`,
          onRemoveSavedRange,
        )}
      <button
        type="button"
        onClick={onClearAll}
        className="ml-auto text-[12px] text-[--color-text-secondary] transition-colors hover:text-[--color-text-primary]"
      >
        Clear all
      </button>
    </div>
  );
}
