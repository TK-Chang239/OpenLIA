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

  it("listProposedSpecs GETs /api/connectors/<id>/proposed-specs", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.listProposedSpecs("abc");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/abc/proposed-specs",
      expect.anything(),
    );
  });

  it("reResolveSpecs POSTs /api/connectors/<id>/proposed-specs/resolve", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.reResolveSpecs("abc");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/abc/proposed-specs/resolve",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listDeptProposedSpecs GETs /api/departments/<id>/proposed-specs", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.listDeptProposedSpecs("macro_research");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs",
      expect.anything(),
    );
  });

  it("resolveDeptProposedSpecs POSTs /api/departments/<id>/proposed-specs/resolve", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.resolveDeptProposedSpecs("macro_research");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs/resolve",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("listDeptResolveEvents GETs per-dept event log", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse([]));
    await connectors.listDeptResolveEvents("macro_research");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs/events",
      expect.anything(),
    );
  });

  it("resolveDeptNeed forwards exclude_connector_ids when provided", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: {},
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: null,
          unsatisfiable: true,
        }),
      );
    await connectors.resolveDeptNeed("macro_research", "real_time_quote", {
      excludeConnectorIds: ["c1", "c2"],
    });
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(
      JSON.stringify({ exclude_connector_ids: ["c1", "c2"] }),
    );
  });

  it("resolveDeptNeed POSTs to per-need resolve endpoint", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({
          department_id: "macro_research",
          need_id: "real_time_quote",
          proposed_spec: {},
          canary_value: null,
          canary_ok: false,
          shape_match: false,
          error: null,
          connector_id: "c1",
          unsatisfiable: false,
        }),
      );
    await connectors.resolveDeptNeed("macro_research", "real_time_quote");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs/real_time_quote/resolve",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("approveDeptSpec POSTs need_id to dept endpoint", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({
          id: "rcs2",
          department_id: "macro_research",
          need_id: "real_time_quote",
          connector_id: "c1",
          access_mode: "cli_mcp",
        }),
      );
    await connectors.approveDeptSpec("macro_research", "real_time_quote");
    expect(spy).toHaveBeenCalledWith(
      "/api/departments/macro_research/proposed-specs/approve",
      expect.objectContaining({ method: "POST" }),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ need_id: "real_time_quote" }));
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

  it("approveSpec POSTs department_id+need_id", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(
        jsonResponse({
          id: "rcs1",
          department_id: "mr",
          need_id: "n",
          connector_id: "c",
          access_mode: "remote_mcp",
        }),
      );
    await connectors.approveSpec("c", "mr", "n");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/c/proposed-specs/approve",
      expect.objectContaining({ method: "POST" }),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(
      JSON.stringify({ department_id: "mr", need_id: "n" }),
    );
  });
});
