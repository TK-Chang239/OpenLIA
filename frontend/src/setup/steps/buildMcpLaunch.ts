/**
 * Turn a parsed MCP input plus the user's confirmed secret selections into a
 * connector launch mode + an extracted secret bag. Selected secrets are
 * replaced in the launch by `{KEY}` placeholders; their values move into the
 * secret bag so the raw key never persists in launch JSON.
 */
import type { ModeIn } from "../../api/connectors";
import type { SecretChip } from "./detectSecrets";
import type { CliParsed, RemoteParsed } from "./parseMcpInput";

export interface BuildMcpLaunchInput {
  parsed: RemoteParsed | CliParsed;
  /** The chips the user confirmed as secrets. */
  selected: SecretChip[];
  /** Optional typed-in secret values, keyed by suggestedKey. */
  values: Record<string, string>;
}

export interface BuiltMcpLaunch {
  mode: ModeIn;
  secrets: Record<string, string>;
}

/** Replace the trailing whitespace-delimited token, or the whole string. */
function placeholderInHeader(value: string, key: string): string {
  if (/\s/.test(value)) {
    return value.replace(/(\S+)\s*$/, `{${key}}`);
  }
  return `{${key}}`;
}

export function buildMcpLaunch(input: BuildMcpLaunchInput): BuiltMcpLaunch {
  const { parsed, selected, values } = input;
  const secrets: Record<string, string> = {};

  const secretValueOf = (chip: SecretChip, extracted: string): void => {
    secrets[chip.suggestedKey] = values[chip.suggestedKey] ?? extracted;
  };

  if (parsed.kind === "remote") {
    const queryByName = new Map<string, SecretChip>();
    const headerByName = new Map<string, SecretChip>();
    for (const c of selected) {
      if (c.locator.kind === "query") queryByName.set(c.locator.name, c);
      if (c.locator.kind === "header") headerByName.set(c.locator.name, c);
    }

    const queryParts = parsed.queryParams.map((p) => {
      const chip = queryByName.get(p.name);
      if (chip) {
        secretValueOf(chip, p.value);
        return `${p.name}={${chip.suggestedKey}}`;
      }
      return `${p.name}=${p.value}`;
    });
    const url =
      queryParts.length > 0
        ? `${parsed.baseUrl}?${queryParts.join("&")}`
        : parsed.baseUrl;

    const headers: Record<string, string> = {};
    for (const h of parsed.headers) {
      const chip = headerByName.get(h.name);
      if (chip) {
        // Extracted value = the credential token (last whitespace segment).
        const token = /\s/.test(h.value)
          ? h.value.trim().split(/\s+/).pop() ?? h.value
          : h.value;
        secretValueOf(chip, token);
        headers[h.name] = placeholderInHeader(h.value, chip.suggestedKey);
      } else {
        headers[h.name] = h.value;
      }
    }

    return { mode: { kind: "remote_mcp", url, headers }, secrets };
  }

  // cli
  const argByIndex = new Map<number, SecretChip>();
  for (const c of selected) {
    if (c.locator.kind === "arg") argByIndex.set(c.locator.index, c);
  }
  const argv = parsed.argv.map((tok, i) => {
    const chip = argByIndex.get(i);
    if (chip) {
      secretValueOf(chip, tok);
      return `{${chip.suggestedKey}}`;
    }
    return tok;
  });

  return { mode: { kind: "cli_mcp", argv, env_keys: [] }, secrets };
}
