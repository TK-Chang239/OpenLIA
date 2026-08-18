/**
 * Engine narratives (Retail Sentiment, Macro Research dashboards) carry
 * ledger-style citation markers like `[^web_2]` / `[^eodhd_1]`, but their
 * API payloads ship no citation table to resolve them against. Until the
 * payloads carry provenance, strip the markers so raw tokens never reach
 * the reader.
 */
const CITATION_MARKER_RE = /\s*\[\^[a-z0-9_]+\]/g;

export function stripCitationMarkers(text: string): string {
  return text.replace(CITATION_MARKER_RE, "").replace(/[ \t]{2,}/g, " ").trim();
}
