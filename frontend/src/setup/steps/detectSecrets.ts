/**
 * Detect which parts of a parsed MCP connection string are likely secrets,
 * pre-selecting credential-looking values. The result drives editable chips;
 * the user can toggle any chip on or off before saving.
 */
import type { CliParsed, RemoteParsed } from "./parseMcpInput";

export type SecretLocator =
  | { kind: "query"; name: string }
  | { kind: "header"; name: string }
  | { kind: "arg"; index: number };

export interface SecretChip {
  locator: SecretLocator;
  /** Human label, e.g. "apikey", "Authorization", "arg #2". */
  label: string;
  /** Current literal value as pasted. */
  rawValue: string;
  /** Whether the detector thinks this is a secret. */
  preselected: boolean;
  /** Suggested env-var-style key name for the secret bag. */
  suggestedKey: string;
}

const SECRET_NAME_RE =
  /(api[_-]?key|apikey|api[_-]?token|access[_-]?token|token|secret|key)/i;

function sanitizeKey(s: string): string {
  return s.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").toUpperCase();
}

function looksLikeCredential(token: string): boolean {
  // Placeholder-shaped: YOUR_API_KEY, <KEY>, {KEY}
  if (/^(your[_-]|<|\{)/i.test(token)) return true;
  // ALLCAPS_WITH_UNDERSCORES of reasonable length
  if (/^[A-Z0-9_]{6,}$/.test(token)) return true;
  // High-entropy: long, mixed letters + digits, no path/flag punctuation
  if (token.length >= 12 && /[A-Za-z]/.test(token) && /[0-9]/.test(token)) {
    return true;
  }
  return false;
}

export function detectSecrets(
  parsed: RemoteParsed | CliParsed,
  providerId: string,
): SecretChip[] {
  const prefix = sanitizeKey(providerId) || "CONNECTOR";

  if (parsed.kind === "remote") {
    const chips: SecretChip[] = [];
    for (const p of parsed.queryParams) {
      chips.push({
        locator: { kind: "query", name: p.name },
        label: p.name,
        rawValue: p.value,
        preselected: SECRET_NAME_RE.test(p.name),
        suggestedKey: `${prefix}_${sanitizeKey(p.name)}`,
      });
    }
    for (const h of parsed.headers) {
      const isAuth = h.name.toLowerCase() === "authorization";
      chips.push({
        locator: { kind: "header", name: h.name },
        label: h.name,
        rawValue: h.value,
        preselected: isAuth || SECRET_NAME_RE.test(h.name),
        suggestedKey: `${prefix}_${sanitizeKey(h.name)}`,
      });
    }
    return chips;
  }

  // cli: candidate = non-flag tokens after the server token.
  const chips: SecretChip[] = [];
  for (let i = 0; i < parsed.argv.length; i++) {
    if (i <= parsed.serverIndex) continue;
    const tok = parsed.argv[i];
    if (tok.startsWith("-")) continue;
    chips.push({
      locator: { kind: "arg", index: i },
      label: `arg #${i}`,
      rawValue: tok,
      preselected: looksLikeCredential(tok),
      suggestedKey: `${prefix}_ARG${i}`,
    });
  }
  return chips;
}
