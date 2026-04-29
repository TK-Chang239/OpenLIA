import { describe, it, expect } from "vitest";
import { parseNpxCommand } from "../parseNpxCommand";

describe("parseNpxCommand", () => {
  it("returns an error when the command does not start with npx", () => {
    const result = parseNpxCommand("node server.js");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/npx/i);
    }
  });

  it("returns an error when no package name follows npx", () => {
    const result = parseNpxCommand("npx -y");
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toMatch(/package/i);
    }
  });

  it("extracts argv and a provider id guess from a plain npx command", () => {
    const result = parseNpxCommand("npx -y newsapi-mcp");
    expect(result).toEqual({
      ok: true,
      providerId: "newsapi",
      argv: ["npx", "-y", "newsapi-mcp"],
    });
  });

  it("strips a scope prefix and 'server-' from the provider id guess", () => {
    const result = parseNpxCommand(
      "npx -y @modelcontextprotocol/server-filesystem /tmp",
    );
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.providerId).toBe("filesystem");
      expect(result.argv).toEqual([
        "npx",
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/tmp",
      ]);
    }
  });

  it("preserves the rest of the argv after the package name", () => {
    const result = parseNpxCommand("npx -y polygon-mcp --transport stdio");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.providerId).toBe("polygon");
      expect(result.argv).toEqual([
        "npx",
        "-y",
        "polygon-mcp",
        "--transport",
        "stdio",
      ]);
    }
  });

  it("trims surrounding whitespace and quotes from the input", () => {
    const result = parseNpxCommand("  'npx -y newsapi-mcp'  ");
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.providerId).toBe("newsapi");
    }
  });
});
