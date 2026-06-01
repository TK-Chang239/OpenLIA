import { describe, it, expect } from "vitest";
import { buildMcpLaunch } from "../buildMcpLaunch";
import type { SecretChip } from "../detectSecrets";
import type { RemoteParsed, CliParsed } from "../parseMcpInput";

describe("buildMcpLaunch", () => {
  it("replaces a selected query secret with a placeholder and extracts it", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://mcp.alphavantage.co/mcp",
      queryParams: [{ name: "apikey", value: "AV12345" }],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "AV12345",
        preselected: true,
        suggestedKey: "ALPHAVANTAGE_APIKEY",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode).toEqual({
      kind: "remote_mcp",
      url: "https://mcp.alphavantage.co/mcp?apikey={ALPHAVANTAGE_APIKEY}",
      headers: {},
    });
    expect(built.secrets).toEqual({ ALPHAVANTAGE_APIKEY: "AV12345" });
  });

  it("uses the typed value over the raw value when provided", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [{ name: "apikey", value: "YOUR_API_KEY" }],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "YOUR_API_KEY",
        preselected: true,
        suggestedKey: "X_APIKEY",
      },
    ];
    const built = buildMcpLaunch({
      parsed,
      selected: chips,
      values: { X_APIKEY: "real-key-123" },
    });
    expect(built.secrets).toEqual({ X_APIKEY: "real-key-123" });
    expect(built.mode.url).toBe("https://x/mcp?apikey={X_APIKEY}");
  });

  it("keeps non-selected query params literal", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [
        { name: "apikey", value: "AV1" },
        { name: "region", value: "us" },
      ],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "AV1",
        preselected: true,
        suggestedKey: "X_APIKEY",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode.url).toBe("https://x/mcp?apikey={X_APIKEY}&region=us");
  });

  it("replaces a selected cli arg with a placeholder and clears env_keys", () => {
    const parsed: CliParsed = {
      kind: "cli",
      argv: ["uvx", "marketdata-mcp-server", "MD_KEY_789"],
      serverIndex: 1,
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "arg", index: 2 },
        label: "arg #2",
        rawValue: "MD_KEY_789",
        preselected: true,
        suggestedKey: "MARKETDATA_ARG2",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode).toEqual({
      kind: "cli_mcp",
      argv: ["uvx", "marketdata-mcp-server", "{MARKETDATA_ARG2}"],
      env_keys: [],
    });
    expect(built.secrets).toEqual({ MARKETDATA_ARG2: "MD_KEY_789" });
  });

  it("url-encodes non-selected query param values", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [
        { name: "apikey", value: "AV1" },
        { name: "q", value: "hello world" },
      ],
      headers: [],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "query", name: "apikey" },
        label: "apikey",
        rawValue: "AV1",
        preselected: true,
        suggestedKey: "X_APIKEY",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode.url).toBe("https://x/mcp?apikey={X_APIKEY}&q=hello%20world");
  });

  it("embeds the placeholder inside a Bearer header value", () => {
    const parsed: RemoteParsed = {
      kind: "remote",
      baseUrl: "https://x/mcp",
      queryParams: [],
      headers: [{ name: "Authorization", value: "Bearer abc123" }],
    };
    const chips: SecretChip[] = [
      {
        locator: { kind: "header", name: "Authorization" },
        label: "Authorization",
        rawValue: "Bearer abc123",
        preselected: true,
        suggestedKey: "X_AUTHORIZATION",
      },
    ];
    const built = buildMcpLaunch({ parsed, selected: chips, values: {} });
    expect(built.mode.headers).toEqual({
      Authorization: "Bearer {X_AUTHORIZATION}",
    });
    expect(built.secrets).toEqual({ X_AUTHORIZATION: "abc123" });
  });
});
