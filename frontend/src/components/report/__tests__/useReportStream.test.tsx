import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useReportStream, useReportStreamAttach } from "../useReportStream";

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

  it("sends multipart/form-data when attachments are provided", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: [],
      }) +
      sseFrame("report.complete", { report_id: "r_1", schema: {} }) +
      sseFrame("report.saved", { report_id: "r_1" });

    const fetchMock = mockFetchStream(body);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useReportStream());
    const file = new File(["hello"], "brief.txt", { type: "text/plain" });
    act(() => {
      result.current.start({
        url: "/api/r",
        body: {
          mode: "stock_initiation",
          user_input: "AAPL",
          session_id: "s1",
        },
        attachments: [file],
      });
    });

    await waitFor(() => expect(result.current.state.status).toBe("complete"));
    const call = fetchMock.mock.calls[0];
    const init = call[1] as RequestInit;
    expect(init.body).toBeInstanceOf(FormData);
    const fd = init.body as FormData;
    expect(fd.get("mode")).toBe("stock_initiation");
    expect(fd.get("user_input")).toBe("AAPL");
    expect(fd.get("session_id")).toBe("s1");
    expect(fd.getAll("files")).toHaveLength(1);
    expect((init.headers as Record<string, string>)["content-type"]).toBeUndefined();
  });

  it("report.tool_call.start inserts a running chip with call_id, tool_name, args_preview", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: [],
      }) +
      sseFrame("report.tool_call.start", {
        report_id: "r_1",
        call_id: "c1",
        tool_name: "search_news",
        args_preview: '{"query":"AAPL"}',
      });

    vi.stubGlobal("fetch", mockFetchStream(body));
    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });

    await waitFor(() =>
      expect(result.current.state.toolCalls).toHaveLength(1),
    );
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: "c1",
      toolName: "search_news",
      argsPreview: '{"query":"AAPL"}',
      status: "running",
    });
  });

  it("report.tool_call matches the prior .start by call_id and flips status to done", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: [],
      }) +
      sseFrame("report.tool_call.start", {
        report_id: "r_1",
        call_id: "c1",
        tool_name: "search_news",
        args_preview: '{"q":"AAPL"}',
      }) +
      sseFrame("report.tool_call", {
        report_id: "r_1",
        call_id: "c1",
        tool_name: "search_news",
        summary: "3 results",
      });

    vi.stubGlobal("fetch", mockFetchStream(body));
    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });

    await waitFor(() =>
      expect(result.current.state.toolCalls[0]?.status).toBe("done"),
    );
    expect(result.current.state.toolCalls).toHaveLength(1);
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: "c1",
      toolName: "search_news",
      argsPreview: '{"q":"AAPL"}',
      status: "done",
      summary: "3 results",
    });
  });

  it("orphan report.tool_call (no prior .start) appends a done chip", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: [],
      }) +
      sseFrame("report.tool_call", {
        report_id: "r_1",
        call_id: "c_orphan",
        tool_name: "fetch_quote",
        summary: "AAPL 198.4",
      });

    vi.stubGlobal("fetch", mockFetchStream(body));
    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });

    await waitFor(() =>
      expect(result.current.state.toolCalls).toHaveLength(1),
    );
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: "c_orphan",
      toolName: "fetch_quote",
      status: "done",
      summary: "AAPL 198.4",
    });
  });

  it("section.start / section.complete drive section state (NEW-14-06)", async () => {
    const body =
      sseFrame("report.start", {
        report_id: "r_1",
        department: "equity_research",
        mode: "stock_initiation",
        section_titles: ["A", "B"],
      }) +
      sseFrame("report.section.start", {
        report_id: "r_1",
        section_id: "a",
        title: "A",
        idx: 0,
        total: 2,
      }) +
      sseFrame("report.section.start", {
        report_id: "r_1",
        section_id: "b",
        title: "B",
        idx: 1,
        total: 2,
      }) +
      sseFrame("report.section.complete", {
        report_id: "r_1",
        section_id: "a",
        blocks: [],
      }) +
      sseFrame("report.complete", { report_id: "r_1", schema: {} }) +
      sseFrame("report.saved", { report_id: "r_1" });

    vi.stubGlobal("fetch", mockFetchStream(body));
    const { result } = renderHook(() => useReportStream());
    act(() => {
      result.current.start({ url: "/api/x", body: {} });
    });
    await waitFor(() => expect(result.current.state.status).toBe("complete"));
    const secs = result.current.state.sections;
    expect(secs.length).toBe(2);
    const a = secs.find((s) => s.id === "a");
    const b = secs.find((s) => s.id === "b");
    expect(a?.status).toBe("done");
    expect(b?.status).toBe("writing");
  });
});

// useReportStreamAttach — GET /reports/{id}/stream via EventSource
describe("useReportStreamAttach", () => {
  let lastES: { url: string; addEventListener: ReturnType<typeof vi.fn>; close: ReturnType<typeof vi.fn> };

  class MockES {
    url: string;
    constructor(u: string) {
      this.url = u;
      lastES = this as typeof lastES;
    }
    addEventListener = vi.fn();
    close = vi.fn();
  }

  it("opens GET /reports/{id}/stream when given a report_id", () => {
    (global as { EventSource?: unknown }).EventSource = MockES;
    renderHook(() => useReportStreamAttach("r_test"));
    expect(lastES.url).toBe("/reports/r_test/stream");
    delete (global as { EventSource?: unknown }).EventSource;
  });

  it("does not open EventSource when reportId is null", () => {
    const opened: string[] = [];
    class TrackES {
      constructor(u: string) { opened.push(u); }
      addEventListener = vi.fn();
      close = vi.fn();
    }
    (global as { EventSource?: unknown }).EventSource = TrackES;
    renderHook(() => useReportStreamAttach(null));
    expect(opened).toHaveLength(0);
    delete (global as { EventSource?: unknown }).EventSource;
  });
});
