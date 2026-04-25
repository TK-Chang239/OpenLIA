/**
 * Secretary department API client.
 *
 * The Secretary chat endpoint is mounted at
 * `/api/departments/secretary/chat`. Server accepts both a `POST` body
 * (`{message, session_id?}`) and a `GET` querystring variant for
 * EventSource consumers. Frontend uses the POST flow for the typed
 * client below; the URL helper covers the GET-string consumers.
 */

export function secretaryChatUrl(sessionId?: string): string {
  const base = '/api/departments/secretary/chat';
  return sessionId ? `${base}?session_id=${encodeURIComponent(sessionId)}` : base;
}
