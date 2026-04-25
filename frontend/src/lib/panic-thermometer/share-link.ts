/**
 * Encode/decode a Panic Thermometer config payload as a URL-safe base64 string
 * suitable for embedding in a query parameter (?cfg=...).
 */

export function encodeShareLink(payload: unknown): string {
  const json = JSON.stringify(payload);
  if (typeof btoa === "function") {
    return btoa(unescape(encodeURIComponent(json)))
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/g, "");
  }
  // Node fallback for vitest: Buffer is available.
  return Buffer.from(json, "utf-8")
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

export function decodeShareLink(token: string): unknown {
  const padded = token.replace(/-/g, "+").replace(/_/g, "/");
  const padLen = (4 - (padded.length % 4)) % 4;
  const full = padded + "=".repeat(padLen);
  let json: string;
  if (typeof atob === "function") {
    json = decodeURIComponent(escape(atob(full)));
  } else {
    json = Buffer.from(full, "base64").toString("utf-8");
  }
  return JSON.parse(json);
}

export function readShareLinkFromUrl(): unknown | null {
  if (typeof window === "undefined") return null;
  const params = new URLSearchParams(window.location.search);
  const token = params.get("cfg");
  if (!token) return null;
  try {
    return decodeShareLink(token);
  } catch {
    return null;
  }
}
