import { useRef, useState } from "react";
import { type LucideProps, FileText, Sheet, Image as ImageIcon, FileCode, File } from "lucide-react";
import { type FileKind, type FileSource, useFileViewer } from "../viewer/FileViewerContext";
import { sourceUrl } from "../viewer/renderers/sourceUrl";
import { SaveToRepoButton } from "./SaveToRepoButton";
import { FileDownloadButton } from "./FileDownloadButton";
import { ReportDownloadMenu } from "./ReportDownloadMenu";

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
  report: FileText,
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
  const triggerRef = useRef<HTMLButtonElement>(null);
  const [saved, setSaved] = useState<boolean>(initialSaved);

  const openViewer = () =>
    open({
      filename,
      kind: fileType,
      metadata,
      source,
      initialSaved: saved,
      trigger: triggerRef.current,
    });

  return (
    <div
      role="group"
      aria-label={`Attachment: ${filename}`}
      data-saved={saved ? "true" : undefined}
      className="group inline-flex max-w-[320px] items-center gap-3 rounded-sm border border-border-subtle bg-bg-elevated px-3 py-2 transition-all duration-normal ease-out hover:border-yellow-600 hover:text-feedback-success"
      style={{ fontFamily: "var(--font-mono)" }}
    >
      <button
        ref={triggerRef}
        type="button"
        onClick={openViewer}
        aria-label={`Open file viewer: ${filename}`}
        className="flex min-w-0 flex-1 items-center gap-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-[--color-accent-primary]"
      >
        <Icon size={14} strokeWidth={1.5} />
        <span className="min-w-0 flex-1">
          <span
            className="block truncate text-[11px] font-medium text-text-primary"
            style={{ maxWidth: 160 }}
          >
            {filename}
          </span>
          <span className="block text-[10px] text-text-secondary">{metadata}</span>
        </span>
      </button>
      <div
        className="ml-2 flex items-center gap-1 opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto group-focus-within:opacity-100 group-focus-within:pointer-events-auto data-[saved=true]:opacity-100 data-[saved=true]:pointer-events-auto"
        data-saved={saved ? "true" : undefined}
        data-chip-action=""
      >
        {reportId !== undefined ? (
          <SaveToRepoButton
            variant="chip"
            reportId={reportId}
            initialSaved={saved}
            onChange={setSaved}
          />
        ) : null}
        {source.kind === "report" ? (
          <ReportDownloadMenu
            variant="chip"
            reportId={source.reportId}
            filename={filename}
          />
        ) : (
          <FileDownloadButton variant="chip" url={sourceUrl(source)} filename={filename} />
        )}
      </div>
    </div>
  );
}
