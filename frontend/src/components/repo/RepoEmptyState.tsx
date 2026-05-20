import { BookOpen, SearchX } from "lucide-react";
import { useTranslation } from "react-i18next";

export interface RepoEmptyStateProps {
  mode: "no-saved" | "no-match";
  onClearFilters?: () => void;
}

export function RepoEmptyState({ mode, onClearFilters }: RepoEmptyStateProps): JSX.Element {
  const { t } = useTranslation();
  if (mode === "no-saved") {
    return (
      <div
        className="flex flex-col items-center justify-center flex-1 gap-3 text-center px-6 py-16"
        data-testid="repo-empty-no-saved"
      >
        <BookOpen size={40} strokeWidth={1.5} className="text-[--color-text-tertiary]" />
        <p className="text-base font-medium text-[--color-text-primary]">{t("repository.empty_no_saved")}</p>
        <p className="text-sm text-[--color-text-secondary]">
          {t("repository.empty_no_saved_sub")}
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
        {t("repository.empty_no_match")}
      </p>
      <p className="text-sm text-[--color-text-secondary]">
        {t("repository.empty_no_match_sub")}
      </p>
      {onClearFilters ? (
        <button
          type="button"
          onClick={onClearFilters}
          className="text-sm text-[--color-accent-primary] hover:underline"
        >
          {t("repository.empty_clear_filters")}
        </button>
      ) : null}
    </div>
  );
}
