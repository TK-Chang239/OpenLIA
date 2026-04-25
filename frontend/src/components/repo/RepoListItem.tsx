import type { KeyboardEvent, MouseEvent } from "react";
import { Download, FileText, Trash2 } from "lucide-react";
import type { RepoRow } from "../../api/repo";
import { departmentBadgeClass, departmentLabel } from "../../lib/department-colors";

export interface RepoListItemProps {
  row: RepoRow;
  downloadUrl: string;
  onOpen: (row: RepoRow) => void;
  onRemove: (row: RepoRow) => void;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

export function RepoListItem({
  row,
  downloadUrl,
  onOpen,
  onRemove,
}: RepoListItemProps): JSX.Element {
  const stop = (e: MouseEvent) => e.stopPropagation();
  const onKey = (e: KeyboardEvent<HTMLLIElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onOpen(row);
    }
  };
  return (
    <li
      role="button"
      tabIndex={0}
      onClick={() => onOpen(row)}
      onKeyDown={onKey}
      className="group flex items-center gap-4 px-4 py-3.5 hover:bg-[--color-surface-hover] cursor-pointer outline-none"
      data-testid="repo-row"
    >
      <FileText
        size={20}
        strokeWidth={1.5}
        className="flex-shrink-0 text-[--color-text-secondary]"
      />
      <div className="flex flex-col min-w-0 flex-1">
        <span className="text-base font-medium text-[--color-text-primary] truncate">
          {row.filename}
        </span>
        <span className="text-xs text-[--color-text-secondary] flex items-center gap-1.5 mt-0.5">
          <span
            className={`text-xs rounded-full px-2 py-0.5 font-medium ${departmentBadgeClass(row.department)}`}
            data-testid="department-badge"
          >
            {departmentLabel(row.department)}
          </span>
          <span>· Generated {formatDate(row.generated_at)}</span>
          <span>· Saved {formatDate(row.saved_at)}</span>
        </span>
      </div>
      <div
        className="flex items-center gap-1 flex-shrink-0 ml-2 opacity-0 group-hover:opacity-100 focus-within:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity"
        onClick={stop}
      >
        <a
          href={downloadUrl}
          target="_blank"
          rel="noreferrer"
          aria-label={`Download ${row.filename}`}
          className="w-7 h-7 rounded-[--radius-sm] flex items-center justify-center text-[--color-text-secondary] hover:bg-[--color-surface-active] hover:text-[--color-text-primary]"
          onClick={stop}
        >
          <Download size={14} strokeWidth={1.5} />
        </a>
        <button
          type="button"
          aria-label={`Remove ${row.filename}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(row);
          }}
          className="w-7 h-7 rounded-[--radius-sm] flex items-center justify-center text-[--color-text-secondary] hover:text-[--color-feedback-error] hover:bg-[--color-feedback-error]/10"
        >
          <Trash2 size={14} strokeWidth={1.5} />
        </button>
      </div>
    </li>
  );
}
