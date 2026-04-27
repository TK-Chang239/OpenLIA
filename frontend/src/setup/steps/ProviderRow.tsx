import { useState } from "react";
import { Trash2, GripVertical, RefreshCw } from "lucide-react";
import type { ConnectorRow, ConnectorSource } from "../../api/connectors";

const SOURCE_LABEL: Record<ConnectorSource, string> = {
  built_in: "built-in",
  remote_mcp: "remote MCP",
  cli_mcp: "CLI MCP",
};

export function ProviderRow({
  row,
  priorityIndex,
  onRemove,
  onRetest,
}: {
  row: ConnectorRow;
  priorityIndex: number;
  onRemove: () => Promise<void> | void;
  onRetest: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);

  const pillCls =
    row.status === "validated"
      ? "bg-[--color-feedback-success]/15 text-[--color-feedback-success]"
      : row.status === "failed"
        ? "bg-[--color-feedback-error]/15 text-[--color-feedback-error]"
        : "bg-[--color-surface-active] text-[--color-text-secondary]";

  const handleRetest = async () => {
    setBusy(true);
    try {
      await onRetest();
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async () => {
    setBusy(true);
    try {
      await onRemove();
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="flex flex-col px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base] mb-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <GripVertical size={14} className="text-[--color-text-tertiary] cursor-grab" />
          <span className="text-xs text-[--color-text-tertiary] w-4">{priorityIndex}</span>
          <span className="text-sm text-[--color-text-primary] font-medium truncate">
            {row.provider_id}
          </span>
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-[--color-surface-hover] text-[--color-text-tertiary] uppercase tracking-wide">
            {SOURCE_LABEL[row.source]}
          </span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${pillCls}`}>{row.status}</span>
        </div>
        <div className="flex items-center gap-1 ml-2">
          <button
            type="button"
            aria-label="Retest provider"
            onClick={handleRetest}
            disabled={busy}
            className="text-[--color-text-secondary] hover:text-[--color-text-primary] disabled:opacity-40"
          >
            <RefreshCw size={14} />
          </button>
          <button
            type="button"
            aria-label="Remove provider"
            onClick={handleRemove}
            disabled={busy}
            className="text-[--color-text-secondary] hover:text-[--color-feedback-error] disabled:opacity-40"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
      {row.status === "failed" && row.last_error ? (
        <p className="text-xs text-[--color-feedback-error] mt-2 ml-7 break-words">
          {row.last_error}
        </p>
      ) : null}
    </li>
  );
}
