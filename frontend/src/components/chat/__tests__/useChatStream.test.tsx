import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useChatStream } from "../useChatStream";

interface PushHandle {
  emit: (type: string, data: unknown) => void;
  closeServer: () => void;
  abort: (reason?: unknown) => void;
  signalAborted: () => boolean;
  request: { url: string; method: string; body: string };
}

interface MockFetchOptions {
  rejectWith?: Error;
  failHttp?: number;
}

function makeMockFetch(opts: MockFetchOptions = {}) {
  const handles: PushHandle[] = [];
  const fetchImpl: typeof fetch = (input, init) => {
    if (opts.rejectWith) {
      return Promise.reject(opts.rejectWith);
    }
    let pushed: (chunk: Uint8Array) => void = () => {};
    let close: () => void = () => {};
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        pushed = (chunk: Uint8Array) => controller.enqueue(chunk);
        close = () => {
          try {
            controller.close();
          } catch {}
        };
      },
    });
    const enc = new TextEncoder();
    const handle: PushHandle = {
      emit: (type, data) => {
        const frame = `event: ${type}\ndata: ${JSON.stringify(data)}\n\n`;
        try {
          pushed(enc.encode(frame));
        } catch {}
      },
      closeServer: () => close(),
      abort: () => {},
      signalAborted: () => false,
      request: {
        url: typeof input === "string" ? input : (input as URL).toString(),
        method: init?.method ?? "GET",
        body: typeof init?.body === "string" ? init.body : "",
      },
    };
    const signal = init?.signal as AbortSignal | undefined;
    if (signal) {
      handle.signalAborted = () => signal.aborted;
      signal.addEventListener("abort", () => {
        close();
      });
    }
    handles.push(handle);
    if (opts.failHttp) {
      return Promise.resolve(
        new Response(null, { status: opts.failHttp }) as Response,
      );
    }
    return Promise.resolve(
      new Response(stream as unknown as BodyInit, {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }) as Response,
    );
  };
  return { fetchImpl, handles };
}

const SESSION = "00000000-0000-4000-8000-000000000001";

beforeEach(() => {
  vi.restoreAllMocks();
});

async function flushFrames() {
  // Allow streamed reader.read() microtasks to flush.
  await new Promise((r) => setTimeout(r, 0));
}

describe("useChatStream", () => {
  it("starts idle, opens stream on send via POST", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    expect(result.current.state.status).toBe("idle");
    act(() => result.current.send("hello"));
    expect(result.current.state.status).toBe("opening");
    await waitFor(() => expect(handles.length).toBe(1));
    expect(handles[0].request.url).toContain(
      `/api/chat/sessions/${SESSION}/stream`,
    );
    expect(handles[0].request.method).toBe("POST");
    expect(JSON.parse(handles[0].request.body)).toEqual({ q: "hello" });
  });

  it("chat.start → thinking, chat.token → streaming", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("hello"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.start", {}));
    await waitFor(() => expect(result.current.state.status).toBe("thinking"));
    act(() => handles[0].emit("chat.token", { text: "Hi " }));
    await waitFor(() => expect(result.current.state.message).toBe("Hi "));
    act(() => handles[0].emit("chat.token", { text: "there." }));
    await waitFor(() => expect(result.current.state.message).toBe("Hi there."));
    expect(result.current.state.status).toBe("streaming");
  });

  it("tool_call.start appends chip, tool_call.result finalizes it", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() =>
      handles[0].emit("chat.tool_call.start", {
        call_id: "c1",
        tool_name: "get_quote",
        args_preview: "AAPL",
      }),
    );
    await waitFor(() =>
      expect(result.current.state.toolCalls[0]?.callId).toBe("c1"),
    );
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: "c1",
      status: "running",
      toolName: "get_quote",
    });
    act(() =>
      handles[0].emit("chat.tool_call.result", {
        call_id: "c1",
        ok: true,
        summary: "Got AAPL",
      }),
    );
    await waitFor(() =>
      expect(result.current.state.toolCalls[0].status).toBe("done"),
    );
    expect(result.current.state.toolCalls[0].summary).toBe("Got AAPL");
  });

  it("tool_call.result ok=false marks chip failed", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() =>
      handles[0].emit("chat.tool_call.start", {
        call_id: "c1",
        tool_name: "t",
        args_preview: "",
      }),
    );
    act(() =>
      handles[0].emit("chat.tool_call.result", {
        call_id: "c1",
        ok: false,
        summary: "Failed",
      }),
    );
    await waitFor(() =>
      expect(result.current.state.toolCalls[0].status).toBe("failed"),
    );
  });

  it("chat.done finalizes stream", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.token", { text: "ok" }));
    act(() => handles[0].emit("chat.done", {}));
    await waitFor(() => expect(result.current.state.status).toBe("done"));
  });

  it("chat.error transitions to error state", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.error", { message: "LLM unavailable" }));
    await waitFor(() => expect(result.current.state.status).toBe("error"));
    expect(result.current.state.errorMessage).toBe("LLM unavailable");
  });

  it("stop() aborts stream and marks status=stopped", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.token", { text: "partial" }));
    await flushFrames();
    act(() => result.current.stop());
    expect(result.current.state.status).toBe("stopped");
    expect(handles[0].signalAborted()).toBe(true);
  });

  it("ignores events received after terminal state", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.done", {}));
    await waitFor(() => expect(result.current.state.status).toBe("done"));
    act(() => handles[0].emit("chat.token", { text: "late" }));
    await flushFrames();
    expect(result.current.state.message).toBe("");
  });

  it("chat.report_thumbnail records inline chunk + flat thumbnail", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.token", { text: "intro " }));
    act(() =>
      handles[0].emit("chat.report_thumbnail", {
        report_id: "r-42",
        filename: "r.pdf",
      }),
    );
    act(() => handles[0].emit("chat.token", { text: " outro" }));
    await waitFor(() =>
      expect(result.current.state.reportThumbnails[0]).toEqual({
        report_id: "r-42",
        filename: "r.pdf",
      }),
    );
    expect(result.current.state.chunks).toEqual([
      { type: "text", text: "intro " },
      { type: "thumbnail", report_id: "r-42", filename: "r.pdf" },
      { type: "text", text: " outro" },
    ]);
  });

  it("transport drop after tokens → stopped (no false error)", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].emit("chat.token", { text: "partial" }));
    await flushFrames();
    // Server closes without terminal event after at least one auto-reconnect.
    act(() => handles[0].closeServer());
    await waitFor(() => expect(handles.length).toBeGreaterThanOrEqual(2));
    act(() => handles[handles.length - 1].closeServer());
    await waitFor(() => expect(result.current.state.status).toBe("stopped"));
  });

  it("transport drop with no tokens → error", async () => {
    const { fetchImpl, handles } = makeMockFetch();
    const { result } = renderHook(() =>
      useChatStream({ sessionId: SESSION, fetchImpl }),
    );
    act(() => result.current.send("x"));
    await waitFor(() => expect(handles.length).toBe(1));
    act(() => handles[0].closeServer());
    // Auto-reconnect once, then surface error.
    await waitFor(() => expect(handles.length).toBeGreaterThanOrEqual(2));
    act(() => handles[handles.length - 1].closeServer());
    await waitFor(() => expect(result.current.state.status).toBe("error"));
  });
});
