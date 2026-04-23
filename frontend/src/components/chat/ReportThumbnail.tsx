import { AttachmentChip } from "./AttachmentChip";
import { kindFromFilename } from "../viewer/FileViewerContext";

interface Props {
  reportId: string;
  filename: string;
  metadata?: string;
}

export function ReportThumbnail({ reportId, filename, metadata }: Props): JSX.Element {
  const kind = kindFromFilename(filename);
  return (
    <AttachmentChip
      filename={filename}
      fileType={kind}
      metadata={metadata ?? kind.toUpperCase()}
      source={{ kind: "report", reportId }}
      reportId={reportId}
    />
  );
}
