import { RecentReport } from "../../api/earnings-update";

interface Props {
  report: RecentReport;
  onOpen: (id: string) => void;
  showExtras?: boolean;
  onDownload?: (id: string) => void;
  onRemove?: (id: string) => void;
  isNew?: boolean;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function ReportRowItem({
  report,
  onOpen,
  showExtras,
  onDownload,
  onRemove,
  isNew = false,
}: Props) {
  return (
    <div
      role="row"
      className="flex items-center gap-4 px-6 py-3.5 border-b border-[--color-border-subtle] hover:bg-[--color-surface-hover] transition-colors duration-[--duration-fast]"
    >
      {isNew ? (
        <span
          aria-label="New"
          className="inline-block w-1.5 h-1.5 rounded-full bg-[--color-accent-primary] flex-shrink-0"
        />
      ) : null}
      <span className="text-sm font-semibold text-[--color-text-primary] w-12 flex-shrink-0">
        {report.subject ?? "—"}
      </span>
      <span className="flex-1 text-base text-[--color-text-primary]">
        {report.title}
      </span>
      <span className="hidden sm:block text-sm text-[--color-text-secondary] flex-shrink-0">
        {formatDate(report.created_at)}
      </span>
      <button
        type="button"
        onClick={() => onOpen(report.id)}
        className="text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover] ml-2"
      >
        Open
      </button>
      {showExtras ? (
        <>
          <button
            type="button"
            onClick={() => onDownload?.(report.id)}
            aria-label="Download"
            className="text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-2"
          >
            ↓
          </button>
          <button
            type="button"
            onClick={() => onRemove?.(report.id)}
            aria-label="Remove"
            className="text-sm text-[--color-text-secondary] hover:text-[--color-feedback-error] ml-2"
          >
            ×
          </button>
        </>
      ) : null}
    </div>
  );
}
