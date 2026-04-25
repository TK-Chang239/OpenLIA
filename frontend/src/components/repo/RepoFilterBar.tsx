import { Search } from "lucide-react";
import type { RepoFacets } from "../../api/repo";
import { FiltersDropdown } from "./FiltersDropdown";

export interface RepoFilterBarProps {
  q: string;
  onQChange: (q: string) => void;
  facets: RepoFacets;
  selectedDepartments: string[];
  generatedFrom: string;
  generatedTo: string;
  savedFrom: string;
  savedTo: string;
  filtersActive: boolean;
  onApplyFilters: (next: {
    departments: string[];
    generated_from: string;
    generated_to: string;
    saved_from: string;
    saved_to: string;
  }) => void;
}

export function RepoFilterBar({
  q,
  onQChange,
  facets,
  selectedDepartments,
  generatedFrom,
  generatedTo,
  savedFrom,
  savedTo,
  filtersActive,
  onApplyFilters,
}: RepoFilterBarProps): JSX.Element {
  return (
    <div className="flex items-center gap-3 px-6 py-3 border-b border-[--color-border-subtle]">
      <div className="relative flex-1">
        <Search
          size={14}
          strokeWidth={1.5}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[--color-text-tertiary]"
        />
        <input
          type="search"
          aria-label="Search filename"
          placeholder="Search reports..."
          value={q}
          onChange={(e) => onQChange(e.target.value)}
          className="w-full h-9 bg-[--color-bg-input] border border-[--color-border-subtle] rounded-[--radius-md] pl-8 pr-3 text-sm text-[--color-text-primary] placeholder:text-[--color-text-tertiary] focus:border-[--color-border-secondary] outline-none"
        />
      </div>
      <FiltersDropdown
        facets={facets}
        selectedDepartments={selectedDepartments}
        generatedFrom={generatedFrom}
        generatedTo={generatedTo}
        savedFrom={savedFrom}
        savedTo={savedTo}
        active={filtersActive}
        onApply={onApplyFilters}
      />
    </div>
  );
}
