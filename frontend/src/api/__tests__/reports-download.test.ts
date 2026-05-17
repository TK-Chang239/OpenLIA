import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { downloadReportBlob, DownloadError, parseFilenameFromHeader } from "../reports";

describe("parseFilenameFromHeader", () => {
  it("extracts the basic filename quoted parameter", () => {
    expect(
      parseFilenameFromHeader('attachment; filename="Acme.pdf"', "fallback")
    ).toBe("Acme.pdf");
  });

  it("prefers RFC5987 filename* over the legacy parameter when both present", () => {
    const cd =
      "attachment; filename=\"AAPL %E2%80%94 Initiation.pdf\"; filename*=UTF-8''AAPL%20%E2%80%94%20Initiation.pdf";
    expect(parseFilenameFromHeader(cd, "fallback")).toBe(
      "AAPL — Initiation.pdf"
    );
  });

  it("returns fallback when header is missing", () => {
    expect(parseFilenameFromHeader(null, "fallback.pdf")).toBe("fallback.pdf");
  });
});

describe("downloadReportBlob", () => {
  let originalFetch: typeof globalThis.fetch;
  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });
  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  it("fetches /api/reports/:id/export/pdf with credentials", async () => {
    const fakeFetch = vi.fn().mockResolvedValue(
      new Response(new Blob(["%PDF"]), {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="Acme.pdf"' },
      })
    );
    globalThis.fetch = fakeFetch as unknown as typeof fetch;

    const result = await downloadReportBlob("abc", "pdf");
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/reports/abc/export/pdf",
      expect.objectContaining({ credentials: "include" })
    );
    expect(result.filename).toBe("Acme.pdf");
    expect(result.blob.size).toBeGreaterThan(0);
  });

  it("fetches /api/reports/:id/export/docx for word format", async () => {
    const fakeFetch = vi.fn().mockResolvedValue(
      new Response(new Blob(["PK"]), {
        status: 200,
        headers: { "content-disposition": 'attachment; filename="Acme.docx"' },
      })
    );
    globalThis.fetch = fakeFetch as unknown as typeof fetch;

    const result = await downloadReportBlob("abc", "docx");
    expect(fakeFetch).toHaveBeenCalledWith(
      "/api/reports/abc/export/docx",
      expect.objectContaining({ credentials: "include" })
    );
    expect(result.filename).toBe("Acme.docx");
  });

  it("throws DownloadError with server detail on non-2xx JSON response", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "no frontend" }), {
        status: 503,
        headers: { "content-type": "application/json" },
      })
    ) as unknown as typeof fetch;

    await expect(downloadReportBlob("abc", "pdf")).rejects.toThrowError(
      /no frontend/
    );
  });

  it("throws DownloadError with generic message on non-2xx without JSON body", async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response("oops", { status: 500 })
    ) as unknown as typeof fetch;

    await expect(downloadReportBlob("abc", "pdf")).rejects.toBeInstanceOf(
      DownloadError
    );
  });
});
