import { type LucideProps, FileText, Sheet, Image as ImageIcon, FileCode, File } from "lucide-react";
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
  initialSaved?: boolean;
}

type LucideIcon = React.ForwardRefExoticComponent<Omit<LucideProps, "ref"> & React.RefAttributes<SVGSVGElement>>;

const ICON: Record<FileKind, LucideIcon> = {
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
  initialSaved = false,
}: Props): JSX.Element {
  const { open } = useFileViewer();
  const Icon = ICON[fileType];

  const openViewer = () => open({ filename, kind: fileType, metadata, source, initialSaved });

  return (
    <div
      className="group inline-flex max-w-[320px] cursor-pointer items-center gap-3 rounded-sm border border-border-subtle bg-bg-elevated px-3 py-2 transition-all duration-normal ease-out hover:border-yellow-600 hover:text-feedback-success"
      style={{ fontFamily: "var(--font-mono)" }}
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
      <Icon size={14} strokeWidth={1.5} />
      <div className="min-w-0 flex-1">
        <p
          className="truncate text-[11px] font-medium text-text-primary"
          style={{ maxWidth: 160 }}
        >
          {filename}
        </p>
        <p className="text-[10px] text-text-secondary">{metadata}</p>
      </div>
      <div
        className="ml-2 flex items-center gap-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
        data-chip-action=""
      >
        {reportId !== undefined ? (
          <SaveToRepoButton variant="chip" reportId={reportId} initialSaved={initialSaved} />
        ) : null}
        <FileDownloadButton variant="chip" url={sourceUrl(source)} filename={filename} />
      </div>
    </div>
  );
}
