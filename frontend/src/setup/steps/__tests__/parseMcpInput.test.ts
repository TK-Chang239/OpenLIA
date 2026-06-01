import { describe, it, expect } from "vitest";
import { parseMcpInput } from "../parseMcpInput";

describe("parseMcpInput", () => {
  it("classifies an https URL as remote and splits query params", () => {
    const r = parseMcpInput("https://mcp.alphavantage.co/mcp?apikey=AV12345");
    expect(r.kind).toBe("remote");
    if (r.kind === "remote") {
      expect(r.baseUrl).toBe("https://mcp.alphavantage.co/mcp");
      expect(r.queryParams).toEqual([{ name: "apikey", value: "AV12345" }]);
      expect(r.headers).toEqual([]);
    }
  });

  it("classifies a uvx command as cli and finds the server token index", () => {
    const r = parseMcpInput("uvx marketdata-mcp-server MD_KEY_789");
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["uvx", "marketdata-mcp-server", "MD_KEY_789"]);
      expect(r.serverIndex).toBe(1);
    }
  });

  it("classifies a bare npx command as cli", () => {
    const r = parseMcpInput("npx -y newsapi-mcp");
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["npx", "-y", "newsapi-mcp"]);
      expect(r.serverIndex).toBe(2);
    }
  });

  it("parses an mcpServers JSON blob into cli argv", () => {
    const json = JSON.stringify({
      mcpServers: { foo: { command: "npx", args: ["-y", "foo-mcp"] } },
    });
    const r = parseMcpInput(json);
    expect(r.kind).toBe("cli");
    if (r.kind === "cli") {
      expect(r.argv).toEqual(["npx", "-y", "foo-mcp"]);
    }
  });

  it("returns an error for empty input", () => {
    const r = parseMcpInput("   ");
    expect(r.kind).toBe("error");
  });

  it("returns an error for a malformed URL", () => {
    const r = parseMcpInput("https://");
    expect(r.kind).toBe("error");
  });
});
