import type { JSX, MutableRefObject } from "react";
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
  activeFilterCount: number;
  searchInputRef?: MutableRefObject<HTMLInputElement | null>;
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
  activeFilterCount,
  searchInputRef,
  onApplyFilters,
}: RepoFilterBarProps): JSX.Element {
  return (
    <div className="flex items-center gap-3 border-b border-[--color-border-subtle] px-6 py-3">
      <div className="relative h-9 flex-1">
        <Search
          size={14}
          strokeWidth={1.5}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[--color-text-tertiary]"
        />
        <input
          ref={searchInputRef}
          type="search"
          aria-label="Search filename"
          placeholder="Search reports by filename..."
          value={q}
          onChange={(e) => onQChange(e.target.value)}
          className="h-full w-full rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] pl-9 pr-3 text-[13.5px] text-[--color-text-primary] placeholder:text-[--color-text-tertiary] outline-none transition-[border-color,box-shadow] focus:border-[--color-text-secondary] focus:shadow-[0_0_0_3px_rgba(212,255,0,0.10)]"
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
        activeCount={activeFilterCount}
        onApply={onApplyFilters}
      />
    </div>
  );
}
