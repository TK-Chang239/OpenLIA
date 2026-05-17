export const downloadUrlForAttachment = (attachmentId: string): string =>
  `/api/chat/attachments/${attachmentId}/download`;
