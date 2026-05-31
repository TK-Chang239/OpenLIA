/**
 * useV3RunStream tests.
 *
 * EventSource is not implemented in jsdom; we stub a controllable
 * FakeEventSource on globalThis for each test so we can dispatch
 * arbitrary event frames synchronously and assert on the resulting
 * hook state.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useV3RunStream } from "../useV3RunStream";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;

  url: string;
  readyState: number = FakeEventSource.OPEN;
  onerror: ((e: Event) => void) | null = null;
  private listeners: Map<string, EventListener[]> = new Map();
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    const list = this.listeners.get(type) ?? [];
    list.push(listener);
    this.listeners.set(type, list);
  }

  dispatch(type: string, payload: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(payload) });
    const list = this.listeners.get(type) ?? [];
    for (const listener of list) {
      listener(event);
    }
  }

  close() {
    this.closed = true;
    this.readyState = FakeEventSource.CLOSED;
  }
}

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource as unknown as typeof EventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("useV3RunStream", () => {
  it("returns idle status when reportId is null", () => {
    const { result } = renderHook(() => useV3RunStream(null));
    expect(result.current.status).toBe("idle");
    expect(result.current.events).toEqual([]);
    expect(FakeEventSource.instances.length).toBe(0);
  });

  it("opens a stream and increments counters as events arrive", async () => {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));

    const source = FakeEventSource.instances[0];
    expect(source.url).toContain("/v3/runs/run-1/events");

    act(() => {
      source.dispatch("run.started", {
        subject: "RKLB.US",
        template_id: "initiation",
      });
    });
    expect(result.current.status).toBe("streaming");
    expect(result.current.events).toHaveLength(1);

    act(() => {
      source.dispatch("tool.called", { turn: 0, tool_name: "web_search" });
      source.dispatch("tool.completed", {
        turn: 0,
        tool_name: "web_search",
        ok: true,
        source_id: "web_1",
      });
    });
    expect(result.current.toolCallsInflight).toBe(0);

    act(() => {
      source.dispatch("section.written", {
        section_id: "overview",
        char_count: 1500,
      });
      source.dispatch("section.written", {
        section_id: "risks",
        char_count: 800,
      });
      source.dispatch("chart.emitted", {
        chart_id: "trend",
        chart_type: "line",
        title: "T",
      });
    });
    expect(result.current.sectionsWritten).toBe(2);
    expect(result.current.chartsEmitted).toBe(1);
  });

  it("transitions to completed and closes the stream on run.completed", async () => {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    const source = FakeEventSource.instances[0];

    act(() => {
      source.dispatch("run.completed", {
        section_count: 6,
        chart_count: 1,
        citation_count: 5,
      });
    });
    expect(result.current.status).toBe("completed");
    expect(source.closed).toBe(true);
  });

  it("flips to cancelled on run.cancelled", async () => {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    const source = FakeEventSource.instances[0];

    act(() => {
      source.dispatch("run.cancelled", { message: "stopped" });
    });
    expect(result.current.status).toBe("cancelled");
    expect(result.current.terminalMessage).toBe("stopped");
  });

  it("uses run.snapshot status to resolve the terminal state for late connections", async () => {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    const source = FakeEventSource.instances[0];

    act(() => {
      source.dispatch("run.snapshot", { status: "failed", error_message: "oops" });
    });
    expect(result.current.status).toBe("failed");
  });

  it("cancel() POSTs to the cancel endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ cancelled: true }),
    } as unknown as Response);
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));

    await act(async () => {
      await result.current.cancel();
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/equity-research/v3/runs/run-1/cancel");
    expect(init.method).toBe("POST");
  });

  it("counts citations from tool.completed frames that carry a source_id", async () => {
    const { result } = renderHook(() => useV3RunStream("run-1"));
    await waitFor(() => expect(FakeEventSource.instances.length).toBe(1));
    const source = FakeEventSource.instances[0];

    act(() => {
      source.dispatch("run.started", { subject: "RKLB.US", model: "x" });
      source.dispatch("tool.completed", { turn: 0, tool_name: "web_search", ok: true, source_id: "web_1" });
      source.dispatch("tool.completed", { turn: 1, tool_name: "calc", ok: true });
      source.dispatch("tool.completed", { turn: 2, tool_name: "web_search", ok: true, source_id: "web_2" });
    });

    expect(result.current.citationsSeen).toBe(2);
  });

  it("tracks elapsedSeconds only after run.started and freezes it on a terminal frame", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-05-31T00:00:00Z"));
    try {
      const { result } = renderHook(() => useV3RunStream("run-1"));
      const source = FakeEventSource.instances[0];

      expect(result.current.elapsedSeconds).toBeNull();

      act(() => {
        source.dispatch("run.started", { subject: "RKLB.US", model: "x" });
      });
      act(() => {
        vi.setSystemTime(new Date("2026-05-31T00:00:03Z"));
        vi.advanceTimersByTime(3000);
      });
      expect(result.current.elapsedSeconds).toBeGreaterThanOrEqual(3);

      act(() => {
        vi.setSystemTime(new Date("2026-05-31T00:00:05Z"));
        source.dispatch("run.completed", { section_count: 6, chart_count: 1, citation_count: 5 });
      });
      const frozen = result.current.elapsedSeconds;
      expect(frozen).toBeGreaterThanOrEqual(5);

      act(() => {
        vi.setSystemTime(new Date("2026-05-31T00:00:09Z"));
        vi.advanceTimersByTime(4000);
      });
      expect(result.current.elapsedSeconds).toBe(frozen);
    } finally {
      vi.useRealTimers();
    }
  });
});
