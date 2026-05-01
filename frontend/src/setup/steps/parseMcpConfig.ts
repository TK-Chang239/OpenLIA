/**
 * Parse a Claude-Desktop / Cursor / Continue-style MCP server config blob into
 * the fields the AddConnectorForm needs (cli_mcp mode).
 *
 * Input shape (the format every MCP server's docs ships):
 *   {
 *     "mcpServers": {
 *       "<provider_id>": {
 *         "command": "npx",
 *         "args": ["-y", "..."],
 *         "env": { "VAR": "value" }
 *       }
 *     }
 *   }
 */

export interface McpSecretRow {
  key: string;
  value: string;
}

export type ParseMcpConfigResult =
  | {
      ok: true;
      providerId: string;
      argv: string[];
      envKeys: string[];
      secrets: McpSecretRow[];
    }
  | { ok: false; error: string };

export function parseMcpConfig(text: string): ParseMcpConfigResult {
  let parsed: unknown;
  try {
    parsed = JSON.parse(text);
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : "JSON parse failed" };
  }

  const servers = (parsed as { mcpServers?: Record<string, unknown> }).mcpServers;
  const entries = Object.entries(servers ?? {});
  if (entries.length === 0) {
    return { ok: false, error: "Missing or empty mcpServers object" };
  }
  const [providerId, raw] = entries[0];
  const entry = raw as { command: string; args?: string[]; env?: Record<string, string> };

  const argv = [entry.command, ...(entry.args ?? [])];
  const env = entry.env ?? {};
  const envKeys = Object.keys(env);
  const secrets = envKeys.map((k) => ({ key: k, value: env[k] }));

  return { ok: true, providerId, argv, envKeys, secrets };
}
