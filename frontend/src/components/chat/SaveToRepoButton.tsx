import { useEffect, useState } from "react";
import { Bookmark, BookmarkCheck, Loader2 } from "lucide-react";
import {
  saveEuRunToRepo,
  saveMbRunToRepo,
  saveToRepo,
  saveV2RunToRepo,
  saveV3RunToRepo,
  unsaveEuRunFromRepo,
  unsaveMbRunFromRepo,
  unsaveFromRepo,
  unsaveV2RunFromRepo,
  unsaveV3RunFromRepo,
} from "../../api/repo";
import { useSavedReportsOptional } from "../repo/SavedReportsContext";

export type SaveToRepoVariant = "chip" | "viewer-header";

/** Which engine produced the artifact. Selects the right repo
 *  endpoint (``/items`` for v1, ``/v2-runs`` for v2.2, ``/v3-runs``
 *  for v3, ``/eu-runs`` for Earnings Update v2, ``/mb-runs`` for
 *  Morning Briefing) and the right SavedReportsContext bucket. */
export type SaveToRepoEngine = "v1" | "v2" | "v3" | "eu" | "mb";

export interface SaveToRepoButtonProps {
  reportId: string;
  initialSaved: boolean;
  variant: SaveToRepoVariant;
  /** Defaults to "v1" so the existing v1 ReportCard call-sites keep
   *  working without changes. */
  engine?: SaveToRepoEngine;
  onChange?: (saved: boolean) => void;
}

type Status = "idle" | "pending" | "error";

export function SaveToRepoButton({
  reportId,
  initialSaved,
  variant,
  engine = "v1",
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

  const ctxIsSaved =
    engine === "v2"
      ? ctx?.isV2Saved(reportId)
      : engine === "v3"
        ? ctx?.isV3Saved(reportId)
        : engine === "eu"
          ? ctx?.isEuSaved(reportId)
          : engine === "mb"
            ? ctx?.isMbSaved(reportId)
            : ctx?.isSaved(reportId);
  const saved = ctxIsSaved || localSaved;

  const ariaLabel = saved ? "Remove from repository" : "Save to repository";

  const onClick = async () => {
    if (status === "pending") return;
    setStatus("pending");
    setErrorMessage(null);
    try {
      if (saved) {
        if (engine === "v2") {
          await unsaveV2RunFromRepo(reportId);
          ctx?.markV2Unsaved(reportId);
        } else if (engine === "v3") {
          await unsaveV3RunFromRepo(reportId);
          ctx?.markV3Unsaved(reportId);
        } else if (engine === "eu") {
          await unsaveEuRunFromRepo(reportId);
          ctx?.markEuUnsaved(reportId);
        } else if (engine === "mb") {
          await unsaveMbRunFromRepo(reportId);
          ctx?.markMbUnsaved(reportId);
        } else {
          await unsaveFromRepo(reportId);
          ctx?.markUnsaved(reportId);
        }
        setLocalSaved(false);
        setAnnouncement("Report removed from Repository");
        onChange?.(false);
      } else {
        if (engine === "v2") {
          await saveV2RunToRepo(reportId);
          ctx?.markV2Saved(reportId);
        } else if (engine === "v3") {
          await saveV3RunToRepo(reportId);
          ctx?.markV3Saved(reportId);
        } else if (engine === "eu") {
          await saveEuRunToRepo(reportId);
          ctx?.markEuSaved(reportId);
        } else if (engine === "mb") {
          await saveMbRunToRepo(reportId);
          ctx?.markMbSaved(reportId);
        } else {
          await saveToRepo(reportId);
          ctx?.markSaved(reportId);
        }
        setLocalSaved(true);
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
