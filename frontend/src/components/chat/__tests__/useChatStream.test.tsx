import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useChatStream } from "../useChatStream";

class MockEventSource {
  listeners: Record<string, ((ev: MessageEvent) => void)[]> = {};
  closed = false;
  static instances: MockEventSource[] = [];

  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (ev: MessageEvent) => void) {
    this.listeners[type] ??= [];
    this.listeners[type].push(cb);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data: unknown) {
    const cbs = this.listeners[type] ?? [];
    for (const cb of cbs) cb(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

function last(): MockEventSource {
  return MockEventSource.instances[MockEventSource.instances.length - 1];
}

const SESSION = "00000000-0000-4000-8000-000000000001";

describe("useChatStream", () => {
  it("starts idle, opens stream on send", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    expect(result.current.state.status).toBe("idle");
    act(() => result.current.send("hello"));
    expect(result.current.state.status).toBe("opening");
    expect(last().url).toContain(`/api/chat/sessions/${SESSION}/stream`);
  });

  it("chat.start → thinking, chat.token → streaming with content", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("hello"));
    act(() => last().emit("chat.start", {}));
    expect(result.current.state.status).toBe("thinking");
    act(() => last().emit("chat.token", { text: "Hi " }));
    expect(result.current.state.status).toBe("streaming");
    expect(result.current.state.message).toBe("Hi ");
    act(() => last().emit("chat.token", { text: "there." }));
    expect(result.current.state.message).toBe("Hi there.");
  });

  it("tool_call.start appends chip, tool_call.result finalizes it", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() =>
      last().emit("chat.tool_call.start", {
        call_id: "c1",
        tool_name: "get_quote",
        args_preview: "AAPL",
      }),
    );
    expect(result.current.state.toolCalls[0]).toMatchObject({
      callId: "c1",
      status: "running",
      toolName: "get_quote",
    });
    act(() =>
      last().emit("chat.tool_call.result", { call_id: "c1", ok: true, summary: "Got AAPL" }),
    );
    expect(result.current.state.toolCalls[0].status).toBe("done");
    expect(result.current.state.toolCalls[0].summary).toBe("Got AAPL");
  });

  it("tool_call.result ok=false marks chip failed", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() =>
      last().emit("chat.tool_call.start", { call_id: "c1", tool_name: "t", args_preview: "" }),
    );
    act(() =>
      last().emit("chat.tool_call.result", { call_id: "c1", ok: false, summary: "Failed" }),
    );
    expect(result.current.state.toolCalls[0].status).toBe("failed");
  });

  it("chat.done finalizes stream and closes event source", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() => last().emit("chat.token", { text: "ok" }));
    act(() => last().emit("chat.done", {}));
    expect(result.current.state.status).toBe("done");
    expect(last().closed).toBe(true);
  });

  it("chat.error transitions to error state", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() => last().emit("chat.error", { message: "LLM unavailable" }));
    expect(result.current.state.status).toBe("error");
    expect(result.current.state.errorMessage).toBe("LLM unavailable");
  });

  it("stop() closes stream and marks status=stopped", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() => last().emit("chat.token", { text: "partial" }));
    act(() => result.current.stop());
    expect(result.current.state.status).toBe("stopped");
    expect(last().closed).toBe(true);
  });

  it("ignores events received after terminal state", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() => last().emit("chat.done", {}));
    act(() => last().emit("chat.token", { text: "late" }));
    expect(result.current.state.message).toBe("");
  });

  it("chat.report_thumbnail records thumbnails", () => {
    const { result } = renderHook(() => useChatStream({ sessionId: SESSION }));
    act(() => result.current.send("x"));
    act(() =>
      last().emit("chat.report_thumbnail", { report_id: "r-42", filename: "r.pdf" }),
    );
    expect(result.current.state.reportThumbnails[0]).toEqual({
      report_id: "r-42",
      filename: "r.pdf",
    });
  });
});
