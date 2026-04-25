import { LayoutGrid, List } from "lucide-react";

export type ViewMode = "list" | "grid";

export interface ViewToggleProps {
  readonly value: ViewMode;
  readonly onChange: (v: ViewMode) => void;
}

export function ViewToggle({ value, onChange }: ViewToggleProps): JSX.Element {
  return (
    <div
      role="tablist"
      aria-label="View mode"
      className="inline-flex border border-[--color-border-subtle] rounded-[--radius-sm] overflow-hidden"
      data-testid="view-toggle"
    >
      <button
        type="button"
        role="tab"
        aria-selected={value === "list"}
        onClick={() => onChange("list")}
        className={`px-2 py-1 text-xs ${value === "list" ? "bg-[--color-surface-hover]" : ""}`}
        data-testid="view-toggle-list"
      >
        <List size={14} aria-hidden="true" />
        <span className="sr-only">List view</span>
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={value === "grid"}
        onClick={() => onChange("grid")}
        className={`px-2 py-1 text-xs ${value === "grid" ? "bg-[--color-surface-hover]" : ""}`}
        data-testid="view-toggle-grid"
      >
        <LayoutGrid size={14} aria-hidden="true" />
        <span className="sr-only">Grid view</span>
      </button>
    </div>
  );
}
