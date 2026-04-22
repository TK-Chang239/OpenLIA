import { Trash2, GripVertical } from "lucide-react";
import type { ProviderRow as Row } from "../../api/setup";

export function ProviderRow({
  row,
  priorityIndex,
  onRemove,
}: {
  row: Row;
  priorityIndex: number;
  onRemove: () => void;
}) {
  const pillCls =
    row.status === "ok"
      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
      : "bg-[--color-feedback-error]/15 text-[--color-feedback-error]";

  return (
    <li className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base] mb-2">
      <div className="flex items-center gap-3">
        <GripVertical size={14} className="text-[--color-text-tertiary] cursor-grab" />
        <span className="text-xs text-[--color-text-tertiary] w-4">{priorityIndex}</span>
        <span className="text-sm text-[--color-text-primary] font-medium">
          {row.provider ?? row.mode}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${pillCls}`}>{row.status}</span>
      </div>
      <button
        type="button"
        aria-label="Remove provider"
        onClick={onRemove}
        className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
      >
        <Trash2 size={14} />
      </button>
    </li>
  );
}
