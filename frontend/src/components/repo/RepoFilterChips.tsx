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
      className="flex items-center gap-1.5 h-7 px-2.5 rounded-full bg-[--color-accent-subtle] border border-[--color-accent-primary]/30 text-sm text-[--color-accent-primary]"
      data-testid="filter-chip"
    >
      <span>{label}</span>
      <button
        type="button"
        aria-label={`Remove filter ${label}`}
        onClick={onRemove}
        className="inline-flex items-center justify-center"
      >
        <X size={12} strokeWidth={1.5} />
      </button>
    </span>
  );

  return (
    <div
      className="flex items-center flex-wrap gap-2 px-6 py-2 border-b border-[--color-border-subtle]"
      data-testid="filter-chips"
    >
      {q !== "" && chip("q", `Search: "${q}"`, onRemoveSearch)}
      {departments.map((d) =>
        chip(`dept-${d}`, departmentLabel(d), () => onRemoveDepartment(d)),
      )}
      {(generatedFrom || generatedTo) &&
        chip(
          "gen-range",
          `Generated: ${formatRange(generatedFrom, generatedTo)}`,
          onRemoveGeneratedRange,
        )}
      {(savedFrom || savedTo) &&
        chip(
          "saved-range",
          `Saved: ${formatRange(savedFrom, savedTo)}`,
          onRemoveSavedRange,
        )}
      <button
        type="button"
        onClick={onClearAll}
        className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-auto"
      >
        Clear all
      </button>
    </div>
  );
}
