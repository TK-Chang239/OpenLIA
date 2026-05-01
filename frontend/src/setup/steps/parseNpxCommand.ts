/**
 * Parse a bare `npx ...` command (the form most MCP servers' READMEs show
 * outside of a Claude-Desktop config blob) into the fields the
 * AddConnectorForm needs for `cli_mcp` mode.
 *
 * Accepted forms:
 *   npx -y newsapi-mcp
 *   npx -y @modelcontextprotocol/server-filesystem /tmp
 *   npx -y polygon-mcp --transport stdio
 */

export type ParseNpxCommandResult =
  | {
      ok: true;
      providerId: string;
      argv: string[];
    }
  | { ok: false; error: string };

function guessProviderId(pkg: string): string {
  let id = pkg;
  const slash = id.lastIndexOf("/");
  if (id.startsWith("@") && slash !== -1) {
    id = id.slice(slash + 1);
  }
  if (id.startsWith("server-")) id = id.slice("server-".length);
  if (id.endsWith("-mcp")) id = id.slice(0, -"-mcp".length);
  return id;
}

export function parseNpxCommand(text: string): ParseNpxCommandResult {
  const stripped = text.trim().replace(/^['"]|['"]$/g, "").trim();
  const tokens = stripped.split(/\s+/).filter(Boolean);

  if (tokens[0] !== "npx") {
    return { ok: false, error: "Command must start with 'npx'" };
  }

  const pkg = tokens.slice(1).find((t) => !t.startsWith("-"));
  if (!pkg) {
    return { ok: false, error: "No package name found after npx flags" };
  }

  return {
    ok: true,
    providerId: guessProviderId(pkg),
    argv: tokens,
  };
}
