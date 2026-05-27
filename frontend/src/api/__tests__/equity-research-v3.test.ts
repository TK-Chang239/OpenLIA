import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../_request";
import {
  deleteV3Run,
  getV3Run,
  listV3Runs,
  startV3Run,
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
});
