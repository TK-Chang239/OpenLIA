import { useCallback, useEffect, useRef, useState } from "react";
import {
  downloadReportBlob,
  triggerBrowserSave,
  type DownloadFormat,
} from "../../api/reports";
import { useToast } from "../primitives/Toast";

interface ReportDownloadButtonProps {
  readonly reportId: string;
  readonly variant?: "icon" | "primary";
  readonly className?: string;
}

const docxEnabled = (): boolean =>
  String(import.meta.env.VITE_REPORT_DOCX_ENABLED ?? "false").toLowerCase() ===
  "true";

export function ReportDownloadButton({
  reportId,
  variant = "icon",
  className,
}: ReportDownloadButtonProps): JSX.Element {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  const download = useCallback(
    async (fmt: DownloadFormat) => {
      setOpen(false);
      setBusy(true);
      try {
        const { blob, filename } = await downloadReportBlob(reportId, fmt);
        triggerBrowserSave(blob, filename);
      } catch (err) {
        toast.push({
          title: `Download failed: ${(err as Error).message}`,
          tone: "error",
        });
      } finally {
        setBusy(false);
      }
    },
    [reportId, toast],
  );

  const showDocx = docxEnabled();

  return (
    <div
      ref={rootRef}
      className={
        className
          ? `report-download relative inline-block ${className}`
          : "report-download relative inline-block"
      }
      data-busy={busy ? "true" : "false"}
    >
      <button
        type="button"
        aria-label="Download report"
        aria-haspopup="menu"
        aria-expanded={open ? "true" : "false"}
        disabled={busy}
        onClick={() => setOpen((v) => !v)}
        className={
          variant === "primary"
            ? "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[--radius-sm] border border-[--color-border-subtle] bg-[--color-bg-elevated] text-sm text-[--color-text-primary] hover:bg-[--color-bg-hover] disabled:opacity-50"
            : "inline-flex items-center gap-1 p-1.5 rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-bg-hover] disabled:opacity-50"
        }
      >
        {busy ? <Spinner /> : <DownloadIcon />}
        {variant === "primary" && <span>Download</span>}
        <Chevron />
      </button>
      {open && (
        <ul
          role="menu"
          className="absolute right-0 mt-1 z-20 min-w-[170px] rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-elevated] shadow-md py-1 text-sm"
        >
          <li role="none">
            <button
              role="menuitem"
              type="button"
              onClick={() => void download("pdf")}
              className="block w-full text-left px-3 py-1.5 text-[--color-text-primary] hover:bg-[--color-bg-hover]"
            >
              Download as PDF
            </button>
          </li>
          {showDocx && (
            <li role="none">
              <button
                role="menuitem"
                type="button"
                onClick={() => void download("docx")}
                className="block w-full text-left px-3 py-1.5 text-[--color-text-primary] hover:bg-[--color-bg-hover]"
              >
                Download as Word
              </button>
            </li>
          )}
        </ul>
      )}
    </div>
  );
}

function DownloadIcon(): JSX.Element {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      aria-hidden
      focusable="false"
    >
      <path
        d="M8 1v9M4 7l4 4 4-4M2 13h12"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function Spinner(): JSX.Element {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      aria-hidden
      focusable="false"
      className="animate-spin"
    >
      <circle
        cx="8"
        cy="8"
        r="6"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeDasharray="28 12"
      />
    </svg>
  );
}

function Chevron(): JSX.Element {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      aria-hidden
      focusable="false"
    >
      <path
        d="M2 4l3 3 3-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
