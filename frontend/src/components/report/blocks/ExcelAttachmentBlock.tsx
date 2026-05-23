/**
 * ExcelAttachmentBlock — renders a v2.2 `excel_attachment` block.
 *
 * Some v2.2 helpers (financial models, comp tables) produce sidecar
 * spreadsheets. This block renders a download chip in the section flow
 * so the user can grab the .xlsx without leaving the report.
 */
import { Download } from "lucide-react";
import { type JSX } from "react";

export interface ExcelAttachmentBlockProps {
  type: "excel_attachment";
  filename: string;
  download_url: string;
  row_count?: number;
  sheet_count?: number;
}

export function ExcelAttachmentBlock({
  filename,
  download_url,
  row_count,
  sheet_count,
}: ExcelAttachmentBlockProps): JSX.Element {
  const meta: string[] = [];
  if (row_count !== undefined) meta.push(`${row_count} rows`);
  if (sheet_count !== undefined) meta.push(`${sheet_count} sheets`);

  return (
    <a
      href={download_url}
      download={filename}
      className="my-3 inline-flex max-w-full items-center gap-3 rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-2 text-[--color-text-primary] no-underline transition-colors hover:bg-[--color-surface-hover]"
      data-block-type="excel_attachment"
    >
      <Download size={14} strokeWidth={1.7} aria-hidden="true" />
      <span className="flex min-w-0 flex-col">
        <span className="truncate text-[13px] font-medium">{filename}</span>
        {meta.length > 0 ? (
          <span className="font-mono text-[10.5px] tracking-[0.04em] text-[--color-text-tertiary]">
            {meta.join(" · ")}
          </span>
        ) : null}
      </span>
    </a>
  );
}
