import { useEffect, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { SlidersHorizontal } from "lucide-react";
import type { RepoFacets } from "../../api/repo";
import { departmentLabel } from "../../lib/department-colors";

export interface FiltersDropdownProps {
  facets: RepoFacets;
  selectedDepartments: string[];
  generatedFrom: string;
  generatedTo: string;
  savedFrom: string;
  savedTo: string;
  onApply: (next: {
    departments: string[];
    generated_from: string;
    generated_to: string;
    saved_from: string;
    saved_to: string;
  }) => void;
  active: boolean;
  /** Count of active filter chips, rendered as a badge on the trigger. */
  activeCount: number;
}

export function FiltersDropdown({
  facets,
  selectedDepartments,
  generatedFrom,
  generatedTo,
  savedFrom,
  savedTo,
  onApply,
  active,
  activeCount,
}: FiltersDropdownProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const [draftDepartments, setDraftDepartments] = useState<string[]>(selectedDepartments);
  const [draftGenFrom, setDraftGenFrom] = useState(generatedFrom);
  const [draftGenTo, setDraftGenTo] = useState(generatedTo);
  const [draftSavedFrom, setDraftSavedFrom] = useState(savedFrom);
  const [draftSavedTo, setDraftSavedTo] = useState(savedTo);

  // Re-sync drafts when popover opens.
  useEffect(() => {
    if (open) {
      setDraftDepartments(selectedDepartments);
      setDraftGenFrom(generatedFrom);
      setDraftGenTo(generatedTo);
      setDraftSavedFrom(savedFrom);
      setDraftSavedTo(savedTo);
    }
  }, [open, selectedDepartments, generatedFrom, generatedTo, savedFrom, savedTo]);

  const toggleDepartment = (slug: string) => {
    setDraftDepartments((prev) =>
      prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug],
    );
  };

  const apply = () => {
    onApply({
      departments: draftDepartments,
      generated_from: draftGenFrom,
      generated_to: draftGenTo,
      saved_from: draftSavedFrom,
      saved_to: draftSavedTo,
    });
    setOpen(false);
  };

  const triggerActive = active
    ? "border-[--color-accent-primary] bg-[rgba(var(--color-accent-primary-rgb),0.10)] text-[--color-accent-on-tint] hover:border-[--color-accent-primary]"
    : "border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-secondary] hover:border-[--color-text-secondary] hover:text-[--color-text-primary]";

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label="Filters"
          aria-pressed={active}
          className={`inline-flex h-9 items-center gap-[6px] rounded-[--radius-md] border px-3 text-[12.5px] font-medium transition-colors ${triggerActive}`}
        >
          <SlidersHorizontal size={14} strokeWidth={1.6} />
          Filters
          {activeCount > 0 ? (
            <span
              className="ml-[2px] inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[--color-accent-primary] px-[5px] font-mono text-[10px] font-semibold text-[--color-accent-on]"
              data-testid="filters-badge"
            >
              {activeCount}
            </span>
          ) : null}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          className="bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] shadow-md p-4 w-[300px] z-50"
          data-testid="filters-dropdown"
        >
          <div className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mb-2">
            Department
          </div>
          <ul className="mb-4">
            {facets.departments.length === 0 ? (
              <li className="text-sm text-[--color-text-tertiary]">No departments</li>
            ) : (
              facets.departments.map((d) => (
                <li
                  key={d.slug}
                  className="flex items-center gap-2 py-1.5 text-sm text-[--color-text-primary]"
                >
                  <input
                    id={`dept-${d.slug}`}
                    type="checkbox"
                    checked={draftDepartments.includes(d.slug)}
                    onChange={() => toggleDepartment(d.slug)}
                  />
                  <label htmlFor={`dept-${d.slug}`} className="flex-1 cursor-pointer">
                    {departmentLabel(d.slug)}{" "}
                    <span className="text-[--color-text-tertiary]">({d.count})</span>
                  </label>
                </li>
              ))
            )}
          </ul>

          <div className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mb-2">
            Date Generated
          </div>
          <div className="flex gap-2 mb-4">
            <input
              type="date"
              aria-label="Generated from"
              value={draftGenFrom}
              onChange={(e) => setDraftGenFrom(e.target.value)}
              className="flex-1 h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
            />
            <input
              type="date"
              aria-label="Generated to"
              value={draftGenTo}
              onChange={(e) => setDraftGenTo(e.target.value)}
              className="flex-1 h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
            />
          </div>

          <div className="text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] mb-2">
            Date Saved
          </div>
          <div className="flex gap-2">
            <input
              type="date"
              aria-label="Saved from"
              value={draftSavedFrom}
              onChange={(e) => setDraftSavedFrom(e.target.value)}
              className="flex-1 h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
            />
            <input
              type="date"
              aria-label="Saved to"
              value={draftSavedTo}
              onChange={(e) => setDraftSavedTo(e.target.value)}
              className="flex-1 h-8 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-input] px-2 text-sm"
            />
          </div>

          <button
            type="button"
            onClick={apply}
            className="h-8 px-3 rounded-[--radius-md] text-sm w-full mt-3 bg-[--color-accent-primary] text-[--color-accent-on]"
          >
            Apply
          </button>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
