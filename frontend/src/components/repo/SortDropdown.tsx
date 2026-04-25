import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { Check, ChevronDown } from "lucide-react";
import type { RepoSort } from "../../api/repo";

const SORT_LABELS: Record<RepoSort, string> = {
  saved_desc: "Date Saved (newest)",
  saved_asc: "Date Saved (oldest)",
  generated_desc: "Date Generated (newest)",
  generated_asc: "Date Generated (oldest)",
  department_asc: "Department (A→Z)",
  filename_asc: "Filename (A→Z)",
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
  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label="Sort"
          className="flex items-center gap-1 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]"
        >
          <span>Sort: {SORT_LABELS[value]}</span>
          <ChevronDown size={12} strokeWidth={1.5} />
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
                <span>{SORT_LABELS[key]}</span>
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
