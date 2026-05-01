import { describe, it, expect } from "vitest";
import { parseMcpConfig } from "../parseMcpConfig";

describe("parseMcpConfig", () => {
  it("returns an error when mcpServers is missing or empty", () => {
    expect(parseMcpConfig("{}")).toEqual({
      ok: false,
      error: expect.stringMatching(/mcpServers/i),
    });
    expect(parseMcpConfig(JSON.stringify({ mcpServers: {} }))).toEqual({
      ok: false,
      error: expect.stringMatching(/mcpServers/i),
    });
  });

  it("returns an error result for malformed JSON instead of throwing", () => {
    const result = parseMcpConfig("{ not json");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/json|parse/i);
    }
  });

  it("extracts provider_id, argv, env_keys, and secrets from a single-server config", () => {
    const json = JSON.stringify({
      mcpServers: {
        newsapi: {
          command: "npx",
          args: ["-y", "newsapi-mcp"],
          env: { NEWSAPI_KEY: "YOUR_API_KEY_HERE" },
        },
      },
    });

    const result = parseMcpConfig(json);

    expect(result).toEqual({
      ok: true,
      providerId: "newsapi",
      argv: ["npx", "-y", "newsapi-mcp"],
      envKeys: ["NEWSAPI_KEY"],
      secrets: [{ key: "NEWSAPI_KEY", value: "YOUR_API_KEY_HERE" }],
    });
  });
});
