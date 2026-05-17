import { type FileSource } from "../FileViewerContext";
import { downloadUrlForAttachment } from "../../../api/files";

/**
 * Source URL for fetching a viewer file's body (markdown, csv, image, pdf, ...).
 *
 * Only attachment sources reach this function in production. Report sources
 * never call it: reports are rendered via `StructuredReportRenderer` which
 * uses the JSON API (`fetchReport`), and downloads use the shared
 * `<ReportDownloadButton>` (which calls the /export/pdf and /export/docx
 * endpoints directly).
 */
export function sourceUrl(source: FileSource): string {
  if (source.kind === "report") {
    throw new Error(
      "sourceUrl(): report sources don't have a fetchable body URL — use fetchReport()/ReportDownloadButton",
    );
  }
  return downloadUrlForAttachment(source.attachmentId);
}
