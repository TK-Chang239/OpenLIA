import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../_request";
import {
  cancelV3Run,
  deleteV3Run,
  getV3Run,
  listV3Runs,
  startV3Run,
  startV3RunAsync,
  uploadV3Instructions,
  v3EventsUrl,
  v3HtmlUrl,
  v3PdfUrl,
  type V3ReportDetail,
  type V3ReportSummary,
  type V3StartResponse,
} from "../equity-research-v3";

describe("equity-research-v3 api client", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("startV3Run POSTs payload and returns {report_id, result}", async () => {
    const body: V3StartResponse = {
      report_id: "abc-123",
      result: {
        status: "completed",
        subject: "RKLB.US",
        template_id: "initiation",
        message: "",
        sections: [],
        charts: [],
        citations: [],
      },
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await startV3Run({
      subject: "RKLB.US",
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
    });
    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toMatchObject({
      subject: "RKLB.US",
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
    });
  });

  it("listV3Runs GETs the list endpoint with no params by default", async () => {
    const body: V3ReportSummary[] = [];
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await listV3Runs();
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs");
  });

  it("listV3Runs appends status query when provided", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => [],
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await listV3Runs({ status: "completed" });
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs?status=completed");
  });

  it("getV3Run encodes the report id into the path", async () => {
    const body: V3ReportDetail = {
      report: {
        report_id: "abc-123",
        subject: "RKLB.US",
        template_id: "initiation",
        language: "en",
        length: "normal",
        status: "completed",
        created_at: "2026-05-27T00:00:00Z",
        completed_at: "2026-05-27T00:05:00Z",
      },
      error_message: null,
      sections: [],
      charts: [],
      citations: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await getV3Run("abc 123 / foo");
    const [url] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/abc%20123%20%2F%20foo");
  });

  it("deleteV3Run sends DELETE and returns void", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      headers: { get: () => "application/json" },
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await deleteV3Run("xyz");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/xyz");
    expect(init.method).toBe("DELETE");
  });

  it("throws ApiError when the engine is disabled (503)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: { get: () => "application/json" },
      json: async () => ({ detail: "v3 engine disabled" }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      startV3Run({ subject: "x", provider_kind: "anthropic", model: "claude-sonnet-4-6" }),
    ).rejects.toBeInstanceOf(ApiError);
  });

  it("v3HtmlUrl / v3PdfUrl encode the report id", () => {
    expect(v3HtmlUrl("abc-123")).toBe(
      "/api/departments/equity-research/v3/runs/abc-123/html",
    );
    expect(v3PdfUrl("abc-123")).toBe(
      "/api/departments/equity-research/v3/runs/abc-123/pdf",
    );
    expect(v3HtmlUrl("a / b")).toBe(
      "/api/departments/equity-research/v3/runs/a%20%2F%20b/html",
    );
  });

  it("startV3RunAsync POSTs to /runs/start and returns {report_id}", async () => {
    const body = { report_id: "abc-async" };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => body,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await startV3RunAsync({
      subject: "RKLB.US",
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
    });
    expect(result).toEqual(body);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/start");
    expect(init.method).toBe("POST");
  });

  it("cancelV3Run POSTs to the cancel endpoint and returns {cancelled}", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ cancelled: true }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await cancelV3Run("abc-123");
    expect(result).toEqual({ cancelled: true });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/abc-123/cancel");
    expect(init.method).toBe("POST");
  });

  it("startV3RunAsync sends instructions_id in the JSON body", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ report_id: "x" }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    await startV3RunAsync({
      subject: "RKLB.US",
      template_id: "freeform",
      instructions_id: "instr-1",
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
    });
    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse(init.body)).toMatchObject({
      template_id: "freeform",
      instructions_id: "instr-1",
    });
  });

  it("startV3RunAsync (multipart) appends template_id + instructions_id alongside files", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ report_id: "x" }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["bytes"], "deck.pdf", { type: "application/pdf" });
    await startV3RunAsync(
      {
        subject: "RKLB.US",
        template_id: "freeform",
        instructions_id: "instr-1",
        provider_kind: "anthropic",
        model: "claude-sonnet-4-6",
      },
      [file],
    );
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/start");
    const fd = init.body as FormData;
    expect(fd.get("template_id")).toBe("freeform");
    expect(fd.get("instructions_id")).toBe("instr-1");
    expect(fd.getAll("files")).toHaveLength(1);
  });

  it("uploadV3Instructions POSTs multipart name + file and returns the profile", async () => {
    const profile = {
      id: "instr-1",
      name: "Winner framework",
      is_builtin: false,
      created_at: "2026-05-29T00:00:00Z",
      updated_at: "2026-05-29T00:00:00Z",
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      headers: { get: () => "application/json" },
      json: async () => profile,
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const file = new File(["methodology"], "framework.md", { type: "text/markdown" });
    const result = await uploadV3Instructions("Winner framework", file);
    expect(result).toEqual(profile);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/instructions");
    expect(init.method).toBe("POST");
    const fd = init.body as FormData;
    expect(fd.get("name")).toBe("Winner framework");
    expect((fd.get("file") as File).name).toBe("framework.md");
  });

  it("uploadV3Instructions surfaces the server error detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => "application/json" },
      json: async () => ({ detail: "No instruction text could be extracted." }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const file = new File([""], "empty.pdf", { type: "application/pdf" });
    await expect(uploadV3Instructions("x", file)).rejects.toThrow(
      "No instruction text could be extracted.",
    );
  });

  it("v3EventsUrl encodes the report id", () => {
    expect(v3EventsUrl("abc-123")).toBe(
      "/api/departments/equity-research/v3/runs/abc-123/events",
    );
    expect(v3EventsUrl("a / b")).toBe(
      "/api/departments/equity-research/v3/runs/a%20%2F%20b/events",
    );
  });
});
