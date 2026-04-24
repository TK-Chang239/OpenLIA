import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useReportStream } from "../useReportStream";

function sseFrame(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

function mockFetchStream(body: string) {
  const encoder = new TextEncoder();
  const chunks = [encoder.encode(body)];
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(c);
      controller.close();
    },
  });
  const response = new Response(stream, {
    status: 200,
    headers: { "content-type": "text/event-stream" },
  });
  return vi.fn().mockResolvedValue(response);
}

describe("useReportStream", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("parses named-event frames into state transitions", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: ["Thesis", "Valuation"],
      }) +
      sseFrame("report.phase", { report_id: "r_1", phase: "writing" }) +
      sseFrame("report.complete", { report_id: "r_1", schema: {} }) +
      sseFrame("report.saved", { report_id: "r_1" });

    const fetchMock = mockFetchStream(body);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReportStream());

    act(() => {
      result.current.start({ url: "/api/x", body: { mode: "stock_initiation" } });
    });

    await waitFor(() => expect(result.current.state.status).toBe("complete"));
    expect(result.current.state.sectionTitles).toEqual(["Thesis", "Valuation"]);
    expect(result.current.state.reportId).toBe("r_1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/x",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("routes report.error into error state", async () => {
    const body = sseFrame("report.error", { message: "boom" });
    vi.stubGlobal("fetch", mockFetchStream(body));

    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(result.current.state.errorMessage).toBe("boom");
  });

  it("surfaces an error when the HTTP status is non-2xx", async () => {
    const response = new Response("nope", { status: 500 });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response));

    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });

    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(result.current.state.errorMessage).toMatch(/500/);
  });
});
