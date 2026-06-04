import { describe, it, expect, vi, beforeEach } from "vitest";
import * as connectors from "./connectors";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("api/connectors", () => {
  it("listConnectors GETs /api/connectors", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.listConnectors();
    expect(spy).toHaveBeenCalledWith("/api/connectors", expect.anything());
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.method ?? "GET").toBe("GET");
  });

  it("createConnector POSTs to /api/connectors with JSON body", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "c1" }));
    const input: connectors.CreateConnectorInput = {
      provider_id: "eodhd",
      display_name: "EODHD",
      source: "remote_mcp",
      category: "financial",
      launch: { modes: [{ kind: "remote_mcp", url: "https://x" }] },
      secrets: { API_KEY: "k" },
    };
    await connectors.createConnector(input);
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors",
      expect.objectContaining({ method: "POST" }),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify(input));
  });

  it("deleteConnector DELETEs /api/connectors/<id>", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));
    await connectors.deleteConnector("abc");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/abc",
      expect.objectContaining({ method: "DELETE" }),
    );
  });

  it("validateConnector POSTs /api/connectors/<id>/validate", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "abc" }));
    await connectors.validateConnector("abc");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/abc/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("createConnector forwards grounding URLs in body", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "c1" }));
    const input: connectors.CreateConnectorInput = {
      provider_id: "eodhd",
      display_name: "EODHD",
      source: "remote_mcp",
      category: "financial",
      launch: { modes: [{ kind: "remote_mcp", url: "https://x" }] },
      source_repo_url: "https://github.com/x/y",
      source_repo_revision: "main",
      openapi_url: "https://x/openapi.json",
    };
    await connectors.createConnector(input);
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify(input));
  });

});

describe("listBuiltinTemplates", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("GETs /api/connectors/builtins and returns the list", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse([
        {
          template_id: "firecrawl",
          display_name: "Firecrawl",
          category: "web_search",
          api_key_env_var: "FIRECRAWL_API_KEY",
          covered_need_ids: ["usd_fx_reserve_share"],
        },
      ]),
    );
    const result = await connectors.listBuiltinTemplates();
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/builtins",
      expect.anything(),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.method ?? "GET").toBe("GET");
    expect(result).toHaveLength(1);
    expect(result[0].template_id).toBe("firecrawl");
  });
});

describe("installBuiltin", () => {
  beforeEach(() => { vi.restoreAllMocks(); });

  it("POSTs to /api/connectors/install-builtin with the body", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({
        id: "abc",
        provider_id: "firecrawl",
        display_name: "Firecrawl",
        source: "built_in",
        category: "web_search",
        status: "validated",
        last_error: null,
        cached_tools_count: 0,
      }),
    );
    const result = await connectors.installBuiltin({
      template_id: "firecrawl",
      api_key: "k",
    });
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/install-builtin",
      expect.objectContaining({ method: "POST" }),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(
      JSON.stringify({ template_id: "firecrawl", api_key: "k" }),
    );
    expect(result.provider_id).toBe("firecrawl");
  });
});
