import { useState } from "react";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import { saveToRepo, unsaveFromRepo } from "../../api/repo";

export type SaveToRepoVariant = "chip" | "viewer-header";

export interface SaveToRepoButtonProps {
  reportId: string;
  initialSaved: boolean;
  variant: SaveToRepoVariant;
  onChange?: (saved: boolean) => void;
}

type Status = "idle" | "pending" | "error";

export function SaveToRepoButton({
  reportId,
  initialSaved,
  variant,
  onChange,
}: SaveToRepoButtonProps): JSX.Element {
  const [saved, setSaved] = useState(initialSaved);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const label = saved ? "Remove from repository" : "Save to repository";

  const onClick = async () => {
    setStatus("pending");
    setErrorMessage(null);
    try {
      if (saved) {
        await unsaveFromRepo(reportId);
        setSaved(false);
        onChange?.(false);
      } else {
        await saveToRepo(reportId);
        setSaved(true);
        onChange?.(true);
      }
      setStatus("idle");
    } catch {
      setStatus("error");
      setErrorMessage(saved ? "Could not remove from repository" : "Could not save to repository");
    }
  };

  const Icon = status === "pending" ? Loader2 : saved ? BookmarkCheck : Bookmark;
  const iconSize = variant === "chip" ? 14 : 16;

  const baseClasses =
    variant === "chip"
      ? "inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      : "inline-flex items-center gap-1.5 rounded-[--radius-md] px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]";

  return (
    <>
      <button
        type="button"
        aria-label={label}
        aria-pressed={saved}
        title={label}
        disabled={status === "pending"}
        onClick={onClick}
        className={baseClasses}
      >
        <Icon
          size={iconSize}
          className={status === "pending" ? "animate-spin" : ""}
          aria-hidden
        />
        {variant === "viewer-header" ? <span>{saved ? "Saved" : "Save"}</span> : null}
      </button>
      {errorMessage ? (
        <span role="alert" className="sr-only" aria-live="polite">
          {errorMessage}
        </span>
      ) : null}
    </>
  );
}
