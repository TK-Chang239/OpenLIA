import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";

import { useNotificationsStream } from "./useNotificationsStream";

let lastEventSource: any;
beforeEach(() => {
  class MockES {
    listeners = new Map<string, ((e: any) => void)[]>();
    url: string;
    constructor(url: string) {
      this.url = url;
      lastEventSource = this;
    }
    addEventListener(type: string, fn: any) {
      this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]);
    }
    close() {}
    fire(type: string, payload: any) {
      (this.listeners.get(type) ?? []).forEach((fn) => fn({ data: JSON.stringify(payload) }));
    }
  }
  (global as any).EventSource = MockES;
});
afterEach(() => {
  delete (global as any).EventSource;
});

describe("useNotificationsStream", () => {
  it("opens an EventSource at /notifications/stream", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    expect(lastEventSource.url).toBe("/notifications/stream");
  });

  it("fires a success toast on report.complete", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    lastEventSource.fire("report.complete", { report_id: "r1", title: "MSFT" });
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining("MSFT"),
      expect.anything(),
    );
  });

  it("fires an error toast on report.failed", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    renderHook(() => useNotificationsStream({ navigate, toast }));
    lastEventSource.fire("report.failed", { report_id: "r1", failure_reason: "oops" });
    expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining("oops"),
      expect.anything(),
    );
  });

  it("invokes onAttachedReportChanged when chat.attached_report_changed fires", () => {
    const navigate = vi.fn();
    const toast = { success: vi.fn(), error: vi.fn(), info: vi.fn() };
    const onAttachedReportChanged = vi.fn();
    renderHook(() =>
      useNotificationsStream({ navigate, toast, onAttachedReportChanged })
    );
    lastEventSource.fire("chat.attached_report_changed", {
      session_id: "sess_test", new_report_id: "r_new",
    });
    expect(onAttachedReportChanged).toHaveBeenCalledWith({
      session_id: "sess_test", new_report_id: "r_new",
    });
  });
});
