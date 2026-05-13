interface Props {
  departments: string[];
  assigned: Set<string>;
  onToggle: (deptId: string) => void;
  disabled?: boolean;
}

function humanize(id: string): string {
  return id.replaceAll('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function DepartmentChips({
  departments,
  assigned,
  onToggle,
  disabled,
}: Props): JSX.Element {
  return (
    <div className="flex flex-wrap gap-1">
      {departments.map((d) => {
        const active = assigned.has(d);
        return (
          <button
            type="button"
            key={d}
            disabled={disabled}
            data-active={active}
            onClick={() => onToggle(d)}
            aria-label={`${humanize(d)}${active ? ' (default)' : ''}`}
            className={`rounded-full border px-2 py-0.5 text-xs ${
              active
                ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                : 'border-border-subtle text-text-secondary hover:bg-surface-hover'
            }`}
          >
            {humanize(d)}
          </button>
        );
      })}
    </div>
  );
}
