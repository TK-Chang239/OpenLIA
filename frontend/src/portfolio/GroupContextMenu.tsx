import { Pencil, Move, Trash2 } from "lucide-react";

export interface GroupContextMenuProps {
  readonly group: string;
  readonly onRename: (group: string) => void;
  readonly onReorder: () => void;
  readonly onDelete: (group: string) => void;
  readonly onClose: () => void;
}

export function GroupContextMenu({
  group,
  onRename,
  onReorder,
  onDelete,
  onClose,
}: GroupContextMenuProps): JSX.Element {
  return (
    <div
      role="menu"
      aria-label={`Group ${group} actions`}
      className="absolute z-30 mt-1 bg-[--color-surface-elevated] border border-[--color-border-subtle] rounded-[--radius-sm] shadow text-sm"
      data-testid="group-context-menu"
    >
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onRename(group);
          onClose();
        }}
        className="flex items-center gap-2 w-full px-3 py-1.5 text-left hover:bg-[--color-surface-hover]"
      >
        <Pencil size={14} aria-hidden="true" /> Rename
      </button>
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onReorder();
          onClose();
        }}
        className="flex items-center gap-2 w-full px-3 py-1.5 text-left hover:bg-[--color-surface-hover]"
      >
        <Move size={14} aria-hidden="true" /> Reorder…
      </button>
      <button
        type="button"
        role="menuitem"
        onClick={() => {
          onDelete(group);
          onClose();
        }}
        className="flex items-center gap-2 w-full px-3 py-1.5 text-left hover:bg-[--color-surface-hover] text-[--color-feedback-error]"
        data-testid="group-context-delete"
      >
        <Trash2 size={14} aria-hidden="true" /> Delete
      </button>
    </div>
  );
}
