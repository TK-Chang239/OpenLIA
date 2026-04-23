export const downloadUrlForReport = (reportId: string): string =>
  `/api/reports/${reportId}/download`;

export const downloadUrlForAttachment = (attachmentId: string): string =>
  `/api/chat/attachments/${attachmentId}/download`;
