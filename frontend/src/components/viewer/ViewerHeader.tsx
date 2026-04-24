import { X } from "lucide-react";
import { type FileSource } from "./FileViewerContext";
import { sourceUrl } from "./renderers/sourceUrl";
import { SaveToRepoButton } from "../chat/SaveToRepoButton";
import { FileDownloadButton } from "../chat/FileDownloadButton";

interface Props {
  filename: string;
  metadata: string;
  source: FileSource;
  reportId?: string;
  initialSaved?: boolean;
  onClose: () => void;
}

export function ViewerHeader({
  filename,
  metadata,
  source,
  reportId,
  initialSaved = false,
  onClose,
}: Props): JSX.Element {
  return (
    <div className="flex min-h-[56px] flex-shrink-0 items-start justify-between gap-3 border-b border-border-subtle bg-bg-elevated px-4 py-3">
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="truncate text-[14px] font-medium font-display text-text-primary">{filename}</p>
        <p className="mt-0.5 truncate ol-label-sm">{metadata}</p>
      </div>
      <div className="ml-2 flex flex-shrink-0 items-center gap-1.5">
        {reportId !== undefined ? (
          <SaveToRepoButton variant="viewer-header" reportId={reportId} initialSaved={initialSaved} />
        ) : null}
        <FileDownloadButton variant="viewer-header" url={sourceUrl(source)} filename={filename} />
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover hover:text-text-primary"
        >
          <X size={14} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
