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
      source: "built_in",
      category: "financial",
      launch: { kind: "built_in", template_id: "eodhd" },
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

  it("revalidateConnector POSTs /api/connectors/<id>/validate", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ id: "abc" }));
    await connectors.revalidateConnector("abc");
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/abc/validate",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("scopeAll(undefined) POSTs {connector_ids: null}", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ scoped: 0, per_connector: [] }));
    await connectors.scopeAll();
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/review/scope",
      expect.objectContaining({ method: "POST" }),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ connector_ids: null }));
  });

  it("scopeAll([\"a\",\"b\"]) POSTs {connector_ids: [\"a\",\"b\"]}", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ scoped: 0, per_connector: [] }));
    await connectors.scopeAll(["a", "b"]);
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.body).toBe(JSON.stringify({ connector_ids: ["a", "b"] }));
  });

  it("getReview GETs /api/connectors/review", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ departments: [] }));
    await connectors.getReview();
    expect(spy).toHaveBeenCalledWith(
      "/api/connectors/review",
      expect.anything(),
    );
    const init = spy.mock.calls[0][1] as RequestInit;
    expect(init.method ?? "GET").toBe("GET");
  });
});
