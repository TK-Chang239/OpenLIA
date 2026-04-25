export type ReportDownloadFormat = "md" | "pdf" | "docx";

export const downloadUrlForReport = (
  reportId: string,
  format?: ReportDownloadFormat,
): string =>
  format
    ? `/api/reports/${reportId}/download?format=${format}`
    : `/api/reports/${reportId}/download`;

export const downloadUrlForAttachment = (attachmentId: string): string =>
  `/api/chat/attachments/${attachmentId}/download`;
