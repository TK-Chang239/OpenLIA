import { useEffect, useState } from "react";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import { saveToRepo, unsaveFromRepo } from "../../api/repo";
import { useSavedReportsOptional } from "../repo/SavedReportsContext";

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
  const ctx = useSavedReportsOptional();
  const [localSaved, setLocalSaved] = useState<boolean>(initialSaved);
  const [hovering, setHovering] = useState<boolean>(false);
  const [status, setStatus] = useState<Status>("idle");
  const [announcement, setAnnouncement] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Mirror initialSaved prop into local state whenever the prop changes.
  useEffect(() => {
    setLocalSaved(initialSaved);
  }, [initialSaved]);

  const saved = ctx ? ctx.isSaved(reportId) || localSaved : localSaved;

  const ariaLabel = saved ? "Remove from repository" : "Save to repository";

  const onClick = async () => {
    if (status === "pending") return;
    setStatus("pending");
    setErrorMessage(null);
    try {
      if (saved) {
        await unsaveFromRepo(reportId);
        setLocalSaved(false);
        ctx?.markUnsaved(reportId);
        setAnnouncement("Report removed from Repository");
        onChange?.(false);
      } else {
        await saveToRepo(reportId);
        setLocalSaved(true);
        ctx?.markSaved(reportId);
        setAnnouncement("Report saved to Repository");
        onChange?.(true);
      }
      setStatus("idle");
    } catch {
      setStatus("error");
      const msg = saved ? "Could not remove from repository" : "Could not save to repository";
      setErrorMessage(msg);
      setAnnouncement(msg);
    }
  };

  const Icon = status === "pending" ? Loader2 : saved ? BookmarkCheck : Bookmark;
  const iconSize = variant === "chip" ? 14 : 16;

  const headerLabel =
    saved && hovering ? "Remove" : saved ? "Saved" : "Save";

  const baseClasses =
    variant === "chip"
      ? "inline-flex h-6 w-6 items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]"
      : "inline-flex items-center gap-1.5 rounded-[--radius-md] border px-2.5 py-1.5 text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]";

  const savedBorder =
    saved && variant === "viewer-header"
      ? "border-[--color-feedback-success]"
      : variant === "viewer-header"
        ? "border-transparent"
        : "";

  const removeTint =
    saved && hovering && variant === "viewer-header"
      ? "text-[--color-feedback-error] border-[--color-feedback-error]"
      : "";

  return (
    <>
      <button
        type="button"
        aria-label={ariaLabel}
        aria-pressed={saved}
        title={ariaLabel}
        disabled={status === "pending"}
        onClick={onClick}
        onMouseEnter={() => setHovering(true)}
        onMouseLeave={() => setHovering(false)}
        onFocus={() => setHovering(true)}
        onBlur={() => setHovering(false)}
        className={`${baseClasses} ${savedBorder} ${removeTint}`}
        data-saved={saved ? "true" : "false"}
        data-status={status}
      >
        <Icon
          size={iconSize}
          className={status === "pending" ? "animate-spin" : ""}
          aria-hidden
        />
        {variant === "viewer-header" ? <span>{headerLabel}</span> : null}
      </button>
      <span aria-live="polite" className="sr-only">
        {announcement}
      </span>
      {errorMessage ? (
        <span role="alert" className="sr-only">
          {errorMessage}
        </span>
      ) : null}
    </>
  );
}
