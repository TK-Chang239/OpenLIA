/**
 * Classify a pasted MCP connection string and parse it into a structure the
 * smart-paste add flow can render as editable chips.
 *
 * Accepts:
 *   - A remote URL:   https://mcp.example.com/mcp?apikey=KEY
 *   - A CLI command:  uvx some-mcp-server KEY   |   npx -y some-mcp
 *   - An mcpServers JSON blob (delegated to parseMcpConfig for argv)
 */
import { parseMcpConfig } from "./parseMcpConfig";

export interface RemoteParsed {
  kind: "remote";
  baseUrl: string;
  queryParams: { name: string; value: string }[];
  headers: { name: string; value: string }[];
}

export interface CliParsed {
  kind: "cli";
  argv: string[];
  /** index in argv of the resolved server/package token (-1 if none found) */
  serverIndex: number;
}

export type ParseMcpInputResult =
  | RemoteParsed
  | CliParsed
  | { kind: "error"; error: string };

// Command runners that wrap the actual server package/binary.
const RUNNERS = new Set([
  "npx",
  "uvx",
  "uv",
  "bunx",
  "pnpm",
  "node",
  "python",
  "python3",
  "deno",
]);

function tokenize(text: string): string[] {
  return text
    .trim()
    .replace(/^['"]|['"]$/g, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function findServerIndex(argv: string[]): number {
  let i = 0;
  // Skip a leading runner and its sub-command (e.g. `uv run`).
  if (argv.length > 0 && RUNNERS.has(argv[0])) {
    i = 1;
    if (argv[0] === "uv" && argv[1] === "run") i = 2;
  }
  for (; i < argv.length; i++) {
    if (!argv[i].startsWith("-")) return i;
  }
  return -1;
}

export function parseMcpInput(text: string): ParseMcpInputResult {
  const trimmed = text.trim();
  if (trimmed.length === 0) {
    return { kind: "error", error: "Paste a URL or a command." };
  }

  if (/^https?:\/\//i.test(trimmed)) {
    let url: URL;
    try {
      url = new URL(trimmed);
    } catch {
      return { kind: "error", error: "That does not look like a valid URL." };
    }
    if (!url.hostname) {
      return { kind: "error", error: "That does not look like a valid URL." };
    }
    const queryParams = [...url.searchParams.entries()].map(([name, value]) => ({
      name,
      value,
    }));
    return {
      kind: "remote",
      baseUrl: `${url.origin}${url.pathname}`,
      queryParams,
      headers: [],
    };
  }

  if (trimmed.startsWith("{")) {
    const cfg = parseMcpConfig(trimmed);
    if (!cfg.ok) {
      return { kind: "error", error: cfg.error };
    }
    return { kind: "cli", argv: cfg.argv, serverIndex: findServerIndex(cfg.argv) };
  }

  const argv = tokenize(trimmed);
  if (argv.length === 0) {
    return { kind: "error", error: "Paste a URL or a command." };
  }
  return { kind: "cli", argv, serverIndex: findServerIndex(argv) };
}
