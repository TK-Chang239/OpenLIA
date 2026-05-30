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
  if (source.kind === "v2_report") {
    throw new Error(
      "sourceUrl(): v2_report sources are rendered via the v2 HTML endpoint inside StructuredReportRenderer",
    );
  }
  if (source.kind === "v23_report") {
    throw new Error(
      "sourceUrl(): v23_report sources are rendered via the v2.3 payload endpoint inside StructuredReportRenderer",
    );
  }
  if (source.kind === "v3_report") {
    throw new Error(
      "sourceUrl(): v3_report sources are rendered via getV3Run inside V3ReportRenderer",
    );
  }
  if (source.kind === "eu_v2_report") {
    throw new Error(
      "sourceUrl(): eu_v2_report sources are rendered via getRun inside EUV2ReportRenderer",
    );
  }
  return downloadUrlForAttachment(source.attachmentId);
}
