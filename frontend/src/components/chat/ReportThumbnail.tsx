import { AttachmentChip } from "./AttachmentChip";

interface Props {
  reportId: string;
  filename: string;
  metadata?: string;
  initialSaved?: boolean;
}

export function ReportThumbnail({ reportId, filename, metadata, initialSaved }: Props): JSX.Element {
  // Reports render through StructuredReportRenderer, which FileViewer mounts
  // only when the viewer kind is "report". Pass it explicitly — matching how
  // Repository and V3ReportCard open reports — so the report renderer mounts
  // instead of falling through to UnsupportedRenderer.
  return (
    <AttachmentChip
      filename={filename}
      fileType="report"
      metadata={metadata ?? "REPORT"}
      source={{ kind: "report", reportId }}
      reportId={reportId}
      initialSaved={initialSaved}
    />
  );
}
