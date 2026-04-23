import { FileText, Sheet, Image as ImageIcon, FileCode, File } from "lucide-react";
import { type FileKind, type FileSource, useFileViewer } from "../viewer/FileViewerContext";
import { sourceUrl } from "../viewer/renderers/sourceUrl";
import { SaveToRepoButton } from "./SaveToRepoButton";
import { FileDownloadButton } from "./FileDownloadButton";

interface Props {
  filename: string;
  fileType: FileKind;
  metadata: string;
  source: FileSource;
  reportId?: string;
}

const ICON: Record<FileKind, React.ComponentType<{ size: number }>> = {
  pdf: FileText,
  markdown: FileText,
  text: FileText,
  code: FileCode,
  csv: Sheet,
  image: ImageIcon,
  docx: FileText,
  unknown: File,
};

export function AttachmentChip({
  filename,
  fileType,
  metadata,
  source,
  reportId,
}: Props): JSX.Element {
  const { open } = useFileViewer();
  const Icon = ICON[fileType];

  const openViewer = () => open({ filename, kind: fileType, metadata, source });

  return (
    <div
      className="group inline-flex max-w-[320px] cursor-pointer items-center gap-3 rounded-[--radius-lg] border border-[--color-border-subtle] bg-[--color-bg-elevated] px-3 py-2.5 transition-all duration-fast hover:border-[--color-border-secondary] hover:shadow-sm"
      onClick={(e) => {
        if ((e.target as HTMLElement).closest("[data-chip-action]")) return;
        openViewer();
      }}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          openViewer();
        }
      }}
    >
      <Icon size={20} />
      <div className="min-w-0 flex-1">
        <p
          className="truncate text-base font-medium text-[--color-text-primary]"
          style={{ maxWidth: 160 }}
        >
          {filename}
        </p>
        <p className="text-xs text-[--color-text-secondary]">{metadata}</p>
      </div>
      <div
        className="ml-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
        data-chip-action=""
      >
        {reportId !== undefined ? (
          <SaveToRepoButton variant="chip" reportId={reportId} initialSaved={false} />
        ) : null}
        <FileDownloadButton variant="chip" url={sourceUrl(source)} filename={filename} />
      </div>
    </div>
  );
}
