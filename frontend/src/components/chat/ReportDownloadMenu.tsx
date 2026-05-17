import { useEffect, useState, type JSX } from "react";
import * as DropdownMenu from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Download, Check, AlertTriangle } from "lucide-react";
import { reportDocxUrl, reportPdfUrl } from "../../api/reports";

export type ReportDownloadVariant = "chip" | "viewer-header";

interface Props {
  reportId: string;
  filename: string;
  variant: ReportDownloadVariant;
}

type Status = "idle" | "success" | "error";

const SUCCESS_MS = 1500;
const ERROR_MS = 2000;

function stripExt(name: string): string {
  const i = name.lastIndexOf(".");
  return i > 0 ? name.slice(0, i) : name;
}

function triggerDownload(url: string, filename: string): void {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

export function ReportDownloadMenu({ reportId, filename, variant }: Props): JSX.Element {
  const [status, setStatus] = useState<Status>("idle");
  const [announcement, setAnnouncement] = useState<string>("");

  useEffect(() => {
    if (status === "idle") return;
    const ms = status === "success" ? SUCCESS_MS : ERROR_MS;
    const t = window.setTimeout(() => {
      setStatus("idle");
      setAnnouncement("");
    }, ms);
    return () => window.clearTimeout(t);
  }, [status]);

  const handleDownload = (format: "pdf" | "docx") => {
    const base = stripExt(filename) || `report-${reportId}`;
    const url = format === "pdf" ? reportPdfUrl(reportId) : reportDocxUrl(reportId);
    try {
      triggerDownload(url, `${base}.${format}`);
      setStatus("success");
      setAnnouncement(`Download started (${format.toUpperCase()})`);
    } catch {
      setStatus("error");
      setAnnouncement("Download failed");
    }
  };

  const Icon = status === "success" ? Check : status === "error" ? AlertTriangle : Download;
  const headerLabel =
    status === "success" ? "Downloaded" : status === "error" ? "Failed" : "Download";

  const baseClasses =
    variant === "chip"
      ? "inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      : "inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]";

  return (
    <>
      <DropdownMenu.Root>
        <DropdownMenu.Trigger asChild>
          <button
            type="button"
            aria-label={`Download ${filename}`}
            title={`Download ${filename}`}
            className={baseClasses}
            data-status={status}
          >
            <Icon size={variant === "chip" ? 14 : 16} aria-hidden />
            {variant === "viewer-header" ? (
              <>
                <span>{headerLabel}</span>
                <ChevronDown size={12} strokeWidth={2} aria-hidden />
              </>
            ) : null}
          </button>
        </DropdownMenu.Trigger>
        <DropdownMenu.Portal>
          <DropdownMenu.Content
            sideOffset={4}
            align="end"
            className="z-50 min-w-[180px] rounded-md border border-[--color-border-subtle] bg-[--color-bg-elevated] p-1 text-sm shadow-lg"
          >
            <DropdownMenu.Item
              onSelect={() => handleDownload("pdf")}
              className="cursor-pointer rounded-sm px-2 py-1.5 outline-none data-[highlighted]:bg-[--color-surface-hover]"
            >
              Download as PDF
            </DropdownMenu.Item>
            <DropdownMenu.Item
              onSelect={() => handleDownload("docx")}
              className="cursor-pointer rounded-sm px-2 py-1.5 outline-none data-[highlighted]:bg-[--color-surface-hover]"
            >
              Download as Word (DOCX)
            </DropdownMenu.Item>
          </DropdownMenu.Content>
        </DropdownMenu.Portal>
      </DropdownMenu.Root>
      <span aria-live="polite" className="sr-only">
        {announcement}
      </span>
    </>
  );
}
