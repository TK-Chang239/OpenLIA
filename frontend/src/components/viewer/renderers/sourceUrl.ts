import { type FileSource } from "../FileViewerContext";
import { downloadUrlForAttachment, downloadUrlForReport } from "../../../api/files";

export function sourceUrl(source: FileSource): string {
  return source.kind === "report"
    ? downloadUrlForReport(source.reportId)
    : downloadUrlForAttachment(source.attachmentId);
}
