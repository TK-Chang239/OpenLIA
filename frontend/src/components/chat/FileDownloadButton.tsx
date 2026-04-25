import { useEffect, useState } from "react";
import { Download, Check, AlertTriangle } from "lucide-react";

export type FileDownloadVariant = "chip" | "viewer-header";

export interface FileDownloadButtonProps {
  url: string;
  filename: string;
  variant: FileDownloadVariant;
  onTrigger?: (url: string, filename: string) => void;
  /** When true, the button is disabled and surfaces ``disabledReason`` as a
   *  tooltip. Used when the underlying file is no longer available. */
  disabled?: boolean;
  disabledReason?: string;
}

type Status = "idle" | "success" | "error";

function defaultTrigger(url: string, filename: string) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

const SUCCESS_MS = 1500;
const ERROR_MS = 2000;

export function FileDownloadButton({
  url,
  filename,
  variant,
  onTrigger,
  disabled = false,
  disabledReason,
}: FileDownloadButtonProps): JSX.Element {
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

  const onClick = () => {
    if (disabled) return;
    try {
      (onTrigger ?? defaultTrigger)(url, filename);
      setStatus("success");
      setAnnouncement("Download started");
    } catch {
      setStatus("error");
      setAnnouncement("Download failed");
    }
  };

  const baseLabel = `Download ${filename}`;
  const headerLabel =
    status === "success" ? "Downloaded" : status === "error" ? "Failed" : "Download";
  const Icon = status === "success" ? Check : status === "error" ? AlertTriangle : Download;
  const testId =
    status === "success" ? "download-success" : status === "error" ? "download-error" : undefined;

  const baseClasses =
    variant === "chip"
      ? "inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      : "inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]";

  const tooltip = disabled ? (disabledReason ?? "File no longer available") : baseLabel;

  return (
    <>
      <button
        type="button"
        aria-label={baseLabel}
        aria-disabled={disabled || undefined}
        title={tooltip}
        onClick={onClick}
        className={`${baseClasses} ${disabled ? "cursor-not-allowed opacity-50" : ""}`}
        data-testid={testId}
        data-status={status}
      >
        <Icon size={variant === "chip" ? 14 : 16} aria-hidden />
        {variant === "viewer-header" ? <span>{headerLabel}</span> : null}
      </button>
      <span aria-live="polite" className="sr-only">
        {announcement}
      </span>
    </>
  );
}
