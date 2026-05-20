import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { RepoSort } from "../../api/repo";

const SORT_I18N: Record<RepoSort, string> = {
  saved_desc: "repository.sort_saved_desc",
  saved_asc: "repository.sort_saved_asc",
  generated_desc: "repository.sort_generated_desc",
  generated_asc: "repository.sort_generated_asc",
  department_asc: "repository.sort_department_asc",
  filename_asc: "repository.sort_filename_asc",
};

const ORDER: ReadonlyArray<RepoSort> = [
  "saved_desc",
  "saved_asc",
  "generated_desc",
  "generated_asc",
  "department_asc",
  "filename_asc",
];

export interface SortDropdownProps {
  value: RepoSort;
  onChange: (next: RepoSort) => void;
}

export function SortDropdown({ value, onChange }: SortDropdownProps): JSX.Element {
  const { t } = useTranslation();
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={t("repository.sort_aria")}
          className="inline-flex items-center gap-1 text-[12.5px] text-[--color-text-secondary] transition-colors hover:text-[--color-text-primary]"
        >
          <span>
            {t("repository.sort_label")}{" "}
            <b className="ml-[3px] font-medium text-[--color-text-primary]">
              {t(SORT_I18N[value])}
            </b>
          </span>
          <ChevronDown size={12} strokeWidth={1.8} />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          align="start"
          sideOffset={4}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1 min-w-[220px] z-50"
          data-testid="sort-dropdown"
        >
          {ORDER.map((key) => {
            const active = value === key;
            return (
              <DropdownMenu.Item
                key={key}
                onSelect={() => onChange(key)}
                className={`flex items-center justify-between px-3 py-2 text-sm cursor-pointer outline-none hover:bg-[--color-surface-hover] ${
                  active ? "text-[--color-accent-primary]" : "text-[--color-text-primary]"
                }`}
                data-active={active}
              >
                <span>{t(SORT_I18N[key])}</span>
                {active ? (
                  <Check size={14} strokeWidth={1.5} className="text-[--color-accent-primary]" />
                ) : null}
              </DropdownMenu.Item>
            );
          })}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}
