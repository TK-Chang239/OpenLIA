import { describe, it, expect } from "vitest";
import { detectSecrets } from "../detectSecrets";
import type { RemoteParsed, CliParsed } from "../parseMcpInput";

describe("detectSecrets", () => {
  it("pre-selects an apikey query param and suggests a key name", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://mcp.alphavantage.co/mcp",
      queryParams: [{ name: "apikey", value: "AV12345" }],
      headers: [],
    };
    const chips = detectSecrets(parsed, "alphavantage");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toMatchObject({
      locator: { kind: "query", name: "apikey" },
      rawValue: "AV12345",
      preselected: true,
      suggestedKey: "ALPHAVANTAGE_APIKEY",
    });
  });

  it("does not pre-select a non-credential query param", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [{ name: "region", value: "us" }],
      headers: [],
    };
    const chips = detectSecrets(parsed, "x");
    expect(chips[0].preselected).toBe(false);
  });

  it("pre-selects an Authorization header", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [],
      headers: [{ name: "Authorization", value: "Bearer abc" }],
    };
    const chips = detectSecrets(parsed, "x");
    expect(chips[0]).toMatchObject({
      locator: { kind: "header", name: "Authorization" },
      preselected: true,
    });
  });

  it("pre-selects a credential-looking cli arg after the server token", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["uvx", "marketdata-mcp-server", "MD_KEY_789"],
      serverIndex: 1,
    };
    const chips = detectSecrets(parsed, "marketdata");
    expect(chips).toHaveLength(1);
    expect(chips[0]).toMatchObject({
      locator: { kind: "arg", index: 2 },
      rawValue: "MD_KEY_789",
      preselected: true,
      suggestedKey: "MARKETDATA_ARG2",
    });
  });

  it("ignores flag tokens and the server token itself in cli", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["npx", "-y", "newsapi-mcp"],
      serverIndex: 2,
    };
    const chips = detectSecrets(parsed, "newsapi");
    expect(chips).toEqual([]);
  });

  it("strips leading digits so the suggested key is a valid placeholder name", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://api.3xtrader.com/mcp",
      queryParams: [{ name: "apikey", value: "k" }],
      headers: [],
    };
    const chips = detectSecrets(parsed, "3xtrader");
    // Backend placeholder regex requires the first char to be [A-Za-z_].
    expect(chips[0].suggestedKey).toMatch(/^[A-Za-z_]/);
    expect(chips[0].suggestedKey).toBe("XTRADER_APIKEY");
  });
});
