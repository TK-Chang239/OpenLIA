import { renderHook, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useEuRunStream } from "../useEuRunStream";

class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners = new Map<string, (e: MessageEvent) => void>();
  readyState = 0;
  url: string;
  onerror: ((e: unknown) => void) | null = null;
  constructor(url: string) { this.url = url; FakeEventSource.last = this; }
  addEventListener(t: string, cb: (e: MessageEvent) => void) { this.listeners.set(t, cb); }
  emit(t: string, data: unknown) { this.listeners.get(t)?.({ data: JSON.stringify(data) } as MessageEvent); }
  close() { this.readyState = 2; }
}

beforeEach(() => { (globalThis as unknown as { EventSource: unknown }).EventSource = FakeEventSource as unknown; });
afterEach(() => vi.restoreAllMocks());

describe("useEuRunStream", () => {
  it("counts sections and resolves to completed on run.completed", () => {
    const { result } = renderHook(() => useEuRunStream("r1"));
    act(() => { FakeEventSource.last!.emit("section.written", {}); });
    expect(result.current.sectionsWritten).toBe(1);
    act(() => { FakeEventSource.last!.emit("run.completed", { message: "done" }); });
    expect(result.current.status).toBe("completed");
  });
});
