import { useEffect, useState } from "react";
import { Download, Check, AlertTriangle } from "lucide-react";

export type FileDownloadVariant = "chip" | "viewer-header";

export interface FileDownloadButtonProps {
  url: string;
  filename: string;
  variant: FileDownloadVariant;
  onTrigger?: (url: string, filename: string) => void;
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

export function FileDownloadButton({
  url,
  filename,
  variant,
  onTrigger,
}: FileDownloadButtonProps): JSX.Element {
  const [status, setStatus] = useState<Status>("idle");

  useEffect(() => {
    if (status === "idle") return;
    const ms = status === "success" ? 1500 : 2000;
    const t = window.setTimeout(() => setStatus("idle"), ms);
    return () => window.clearTimeout(t);
  }, [status]);

  const onClick = () => {
    try {
      (onTrigger ?? defaultTrigger)(url, filename);
      setStatus("success");
    } catch {
      setStatus("error");
    }
  };

  const label = `Download ${filename}`;
  const Icon = status === "success" ? Check : status === "error" ? AlertTriangle : Download;
  const testId =
    status === "success" ? "download-success" : status === "error" ? "download-error" : undefined;

  const baseClasses =
    variant === "chip"
      ? "inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      : "inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]";

  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={baseClasses}
      data-testid={testId}
    >
      <Icon size={variant === "chip" ? 14 : 16} aria-hidden />
      {variant === "viewer-header" ? <span>Download</span> : null}
    </button>
  );
}
