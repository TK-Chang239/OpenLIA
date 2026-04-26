import { useState } from "react";
import { Trash2, GripVertical, Pencil, Check, X } from "lucide-react";
import type { ProviderRow as Row } from "../../api/setup";

export function ProviderRow({
  row,
  priorityIndex,
  onRemove,
  onUpdateKey,
}: {
  row: Row;
  priorityIndex: number;
  onRemove: () => void;
  onUpdateKey: (apiKey: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [busy, setBusy] = useState(false);

  const pillCls =
    row.status === "ok"
      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
      : "bg-[--color-feedback-error]/15 text-[--color-feedback-error]";

  const onSave = async () => {
    setBusy(true);
    try {
      await onUpdateKey(apiKey);
      setEditing(false);
      setApiKey("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base] mb-2">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <GripVertical size={14} className="text-[--color-text-tertiary] cursor-grab" />
        <span className="text-xs text-[--color-text-tertiary] w-4">{priorityIndex}</span>
        <span className="text-sm text-[--color-text-primary] font-medium">
          {row.provider ?? row.mode}
        </span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${pillCls}`}>{row.status}</span>
        {editing ? (
          <input
            type="password"
            placeholder="New API key"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="flex-1 h-8 px-2 ml-2 rounded-[--radius-sm] bg-[--color-bg-elevated] border border-[--color-border-subtle] text-sm"
          />
        ) : null}
      </div>
      <div className="flex items-center gap-1 ml-2">
        {editing ? (
          <>
            <button
              type="button"
              aria-label="Save API key"
              onClick={onSave}
              disabled={busy || !apiKey}
              className="text-[--color-feedback-success] disabled:opacity-40"
            >
              <Check size={14} />
            </button>
            <button
              type="button"
              aria-label="Cancel edit"
              onClick={() => {
                setEditing(false);
                setApiKey("");
              }}
              className="text-[--color-text-secondary]"
            >
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              aria-label="Edit API key"
              onClick={() => setEditing(true)}
              className="text-[--color-text-secondary] hover:text-[--color-text-primary]"
            >
              <Pencil size={14} />
            </button>
            <button
              type="button"
              aria-label="Remove provider"
              onClick={onRemove}
              className="text-[--color-text-secondary] hover:text-[--color-feedback-error]"
            >
              <Trash2 size={14} />
            </button>
          </>
        )}
      </div>
    </li>
  );
}
