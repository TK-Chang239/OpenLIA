import type { JSX } from "react";
import { File as FileIcon, X } from "lucide-react";

interface Props {
  filename: string;
  sizeBytes: number;
  /** When provided, the chip renders an `×` remove button. Omit for the
   *  read-only chip used inside the user bubble after send. */
  onRemove?: () => void;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Chip representing an attachment selected in the composer but not yet
 *  uploaded to the backend. Visual treatment matches the design's source
 *  chip but with neutral colors and an optional remove control. */
export function PendingAttachmentChip({
  filename,
  sizeBytes,
  onRemove,
}: Props): JSX.Element {
  return (
    <span
      className="inline-flex items-center gap-[6px] rounded-sm border px-2 py-[3px] font-mono text-[10px]"
      style={{
        borderColor: "var(--color-border-subtle)",
        background: "var(--color-bg-elevated)",
        color: "var(--color-text-secondary)",
      }}
    >
      <FileIcon size={10} strokeWidth={1.5} aria-hidden />
      <span className="max-w-[180px] truncate">{filename}</span>
      <span style={{ color: "var(--color-text-tertiary)" }}>
        {formatSize(sizeBytes)}
      </span>
      {onRemove ? (
        <button
          type="button"
          onClick={onRemove}
          aria-label={`Remove ${filename}`}
          className="ml-[2px] inline-flex items-center justify-center rounded-sm hover:text-text-primary"
          style={{ color: "var(--color-text-tertiary)" }}
        >
          <X size={10} strokeWidth={2} aria-hidden />
        </button>
      ) : null}
    </span>
  );
}
