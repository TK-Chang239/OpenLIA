import type { Ref } from "react";
import { X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { type FileSource } from "./FileViewerContext";
import { sourceUrl } from "./renderers/sourceUrl";
import { SaveToRepoButton } from "../chat/SaveToRepoButton";
import { FileDownloadButton } from "../chat/FileDownloadButton";
import { ReportDownloadButton } from "../report/ReportDownloadButton";

interface Props {
  filename: string;
  metadata: string;
  source: FileSource;
  reportId?: string;
  /** Engine that produced the report — selects the right repo
   *  endpoint. Defaults to "v1" for back-compat with existing v1
   *  callers. */
  saveEngine?: "v1" | "v2" | "v3";
  initialSaved?: boolean;
  hideSaveToRepoButton?: boolean;
  onClose: () => void;
  closeButtonRef?: Ref<HTMLButtonElement>;
}

export function ViewerHeader({
  filename,
  metadata,
  source,
  reportId,
  saveEngine = "v1",
  initialSaved = false,
  hideSaveToRepoButton = false,
  onClose,
  closeButtonRef,
}: Props): JSX.Element {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-[56px] flex-shrink-0 items-start justify-between gap-3 border-b border-border-subtle bg-bg-elevated px-4 py-3">
      <div className="flex min-w-0 flex-1 flex-col">
        <p className="truncate text-[14px] font-medium font-display text-text-primary">{filename}</p>
        <p className="mt-0.5 truncate ol-label-sm">{metadata}</p>
      </div>
      <div className="ml-2 flex flex-shrink-0 items-center gap-1.5">
        {reportId !== undefined && !hideSaveToRepoButton ? (
          <SaveToRepoButton
            variant="viewer-header"
            reportId={reportId}
            engine={saveEngine}
            initialSaved={initialSaved}
          />
        ) : null}
        {source.kind === "report" ? (
          <ReportDownloadButton reportId={source.reportId} />
        ) : source.kind === "v2_report" ? (
          <ReportDownloadButton reportId={source.runId} engine="v2" />
        ) : source.kind === "v23_report" ? (
          <ReportDownloadButton reportId={source.runId} engine="v23" />
        ) : source.kind === "v3_report" ? (
          <ReportDownloadButton reportId={source.reportId} engine="v3" />
        ) : (
          <FileDownloadButton variant="viewer-header" url={sourceUrl(source)} filename={filename} />
        )}
        <button
          ref={closeButtonRef}
          type="button"
          aria-label={t("common.close")}
          onClick={onClose}
          className="flex h-8 w-8 items-center justify-center rounded-md text-text-secondary transition-colors duration-normal ease-out hover:bg-surface-hover hover:text-text-primary"
        >
          <X size={14} strokeWidth={1.5} />
        </button>
      </div>
    </div>
  );
}
