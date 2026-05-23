import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  downloadReportBlob,
  triggerBrowserSave,
  type DownloadFormat,
  type ReportEngine,
} from "../../api/reports";
import { useToast } from "../primitives/Toast";

interface ReportDownloadButtonProps {
  readonly reportId: string;
  readonly variant?: "icon" | "primary";
  readonly className?: string;
  /** Which engine emitted the report — selects the right export URL.
   *  Defaults to "v1" so existing call-sites keep working. */
  readonly engine?: ReportEngine;
}

const docxEnabled = (): boolean =>
  String(import.meta.env.VITE_REPORT_DOCX_ENABLED ?? "true").toLowerCase() !==
  "false";

export function ReportDownloadButton({
  reportId,
  variant = "icon",
  className,
  engine = "v1",
}: ReportDownloadButtonProps): JSX.Element {
  const { t } = useTranslation();
  const toast = useToast();
  const [busy, setBusy] = useState(false);

  const download = useCallback(
    async (fmt: DownloadFormat) => {
      setBusy(true);
      try {
        const { blob, filename } = await downloadReportBlob(reportId, fmt, engine);
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
    [reportId, toast, engine],
  );

  const showDocx = docxEnabled();
  const triggerClass =
    variant === "primary"
      ? "inline-flex items-center gap-1.5 h-[30px] px-3 rounded-md border border-[--color-border-subtle] bg-transparent text-[13px] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary] disabled:opacity-50"
      : "inline-flex items-center gap-1 p-1.5 rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] disabled:opacity-50";

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          type="button"
          aria-label={t("report.aria_download_report")}
          disabled={busy}
          data-busy={busy ? "true" : "false"}
          className={className ? `${triggerClass} ${className}` : triggerClass}
        >
          {busy ? <Spinner /> : <DownloadIcon />}
          {variant === "primary" && <span>{t("report.download")}</span>}
          <Chevron />
        </button>
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={4}
          align="end"
          className="z-50 min-w-[180px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-1 text-sm shadow-lg"
        >
          <DropdownMenu.Item
            onSelect={() => void download("pdf")}
            className="cursor-pointer rounded-sm px-2 py-1.5 outline-none text-[--color-text-primary] data-[highlighted]:bg-[--color-surface-hover]"
          >
            {t("report.download_as_pdf")}
          </DropdownMenu.Item>
          {showDocx && (
            <DropdownMenu.Item
              onSelect={() => void download("docx")}
              className="cursor-pointer rounded-sm px-2 py-1.5 outline-none text-[--color-text-primary] data-[highlighted]:bg-[--color-surface-hover]"
            >
              {t("report.download_as_word")}
            </DropdownMenu.Item>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
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
