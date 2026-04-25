import { BookOpen, SearchX } from "lucide-react";

export interface RepoEmptyStateProps {
  mode: "no-saved" | "no-match";
  onClearFilters?: () => void;
}

export function RepoEmptyState({ mode, onClearFilters }: RepoEmptyStateProps): JSX.Element {
  if (mode === "no-saved") {
    return (
      <div
        className="flex flex-col items-center justify-center flex-1 gap-3 text-center px-6 py-16"
        data-testid="repo-empty-no-saved"
      >
        <BookOpen size={40} strokeWidth={1.5} className="text-[--color-text-tertiary]" />
        <p className="text-base font-medium text-[--color-text-primary]">No saved reports yet.</p>
        <p className="text-sm text-[--color-text-secondary]">
          Save a report from any department to see it here.
        </p>
      </div>
    );
  }
  return (
    <div
      className="flex flex-col items-center justify-center flex-1 gap-3 text-center px-6 py-16"
      data-testid="repo-empty-no-match"
    >
      <SearchX size={40} strokeWidth={1.5} className="text-[--color-text-tertiary]" />
      <p className="text-base font-medium text-[--color-text-primary]">
        No reports match your search.
      </p>
      <p className="text-sm text-[--color-text-secondary]">
        Try adjusting your filters or search terms.
      </p>
      {onClearFilters ? (
        <button
          type="button"
          onClick={onClearFilters}
          className="text-sm text-[--color-accent-primary] hover:underline"
        >
          Clear filters
        </button>
      ) : null}
    </div>
  );
}
