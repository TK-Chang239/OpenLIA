export function secretaryChatUrl(sessionId?: string): string {
  const base = '/api/departments/secretary/chat';
  return sessionId ? `${base}?session_id=${encodeURIComponent(sessionId)}` : base;
}
