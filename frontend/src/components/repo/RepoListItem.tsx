import type { JSX, KeyboardEvent, MouseEvent } from "react";
import { Download, FileText, Trash2 } from "lucide-react";
import type { RepoRow } from "../../api/repo";
import { departmentBadgeClass, departmentLabel } from "../../lib/department-colors";

export interface RepoListItemProps {
  row: RepoRow;
  downloadUrl: string;
  onOpen: (row: RepoRow) => void;
  onRemove: (row: RepoRow) => void;
}

function shortDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    }).toUpperCase();
  } catch {
    return iso;
  }
}

function fileExt(filename: string): string {
  const dot = filename.lastIndexOf(".");
  if (dot < 0 || dot === filename.length - 1) return "FILE";
  return filename.slice(dot + 1).toUpperCase();
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
  const ext = fileExt(row.filename);
  return (
    <li
      role="button"
      tabIndex={0}
      onClick={() => onOpen(row)}
      onKeyDown={onKey}
      className="group relative flex cursor-pointer items-center gap-[14px] px-4 py-[14px] outline-none transition-colors hover:bg-[--color-surface-hover] focus-visible:bg-[--color-surface-hover]"
      data-testid="repo-row"
    >
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] text-[--color-text-secondary]">
        <FileText size={18} strokeWidth={1.5} />
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex min-w-0 items-center gap-[10px]">
          <span className="truncate text-[14.5px] font-medium text-[--color-text-primary]">
            {row.filename}
          </span>
          <span className="flex-shrink-0 whitespace-nowrap rounded-[3px] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-[5px] py-[1px] font-mono text-[9px] tracking-[0.08em] text-[--color-text-tertiary]">
            {ext}
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-[10px] text-[11.5px] text-[--color-text-secondary]">
          <span
            className={`whitespace-nowrap rounded-full px-2 py-[2px] text-[11px] font-medium leading-[1.4] ${departmentBadgeClass(row.department)}`}
            data-testid="department-badge"
          >
            {departmentLabel(row.department)}
          </span>
          <span
            aria-hidden="true"
            className="inline-block h-[2px] w-[2px] rounded-full bg-[--color-text-tertiary]"
          />
          <span className="whitespace-nowrap font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary]">
            Generated{" "}
            <b className="font-medium text-[--color-text-secondary]">
              {shortDate(row.generated_at)}
            </b>
          </span>
          <span
            aria-hidden="true"
            className="inline-block h-[2px] w-[2px] rounded-full bg-[--color-text-tertiary]"
          />
          <span className="whitespace-nowrap font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary]">
            Saved{" "}
            <b className="font-medium text-[--color-text-secondary]">
              {shortDate(row.saved_at)}
            </b>
          </span>
        </div>
      </div>

      <div
        className="ml-2 flex flex-shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 [@media(hover:none)]:opacity-100"
        onClick={stop}
      >
        <a
          href={downloadUrl}
          target="_blank"
          rel="noreferrer"
          aria-label={`Download ${row.filename}`}
          className="flex h-[30px] w-[30px] items-center justify-center rounded-[5px] text-[--color-text-secondary] transition-colors hover:bg-[--color-surface-active] hover:text-[--color-text-primary]"
          onClick={stop}
        >
          <Download size={14} strokeWidth={1.6} />
        </a>
        <button
          type="button"
          aria-label={`Remove ${row.filename}`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(row);
          }}
          className="flex h-[30px] w-[30px] items-center justify-center rounded-[5px] text-[--color-text-secondary] transition-colors hover:bg-[--color-feedback-error]/10 hover:text-[--color-feedback-error]"
        >
          <Trash2 size={14} strokeWidth={1.6} />
        </button>
      </div>
    </li>
  );
}
