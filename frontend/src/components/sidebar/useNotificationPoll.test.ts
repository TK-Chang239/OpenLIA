import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import {
  useNotificationPoll,
  NOTIFICATION_POLL_MS,
} from "./useNotificationPoll";

describe("useNotificationPoll", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    global.fetch = originalFetch;
  });

  it("fetches unread on mount and exposes by_department map", async () => {
    global.fetch = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 2, by_department: { morning_briefing: 2 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ) as unknown as typeof fetch;

    const { result } = renderHook(() => useNotificationPoll());

    await vi.waitFor(() => {
      expect(result.current.unreadByDepartment.morning_briefing).toBe(2);
    });
  });

  it("polls again after NOTIFICATION_POLL_MS", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;

    renderHook(() => useNotificationPoll());

    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1));

    await act(async () => {
      await vi.advanceTimersByTimeAsync(NOTIFICATION_POLL_MS);
    });

    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
  });

  it("markRead POSTs and refreshes the counts", async () => {
    const responses = [
      new Response(
        JSON.stringify({ total: 1, by_department: { morning_briefing: 1 } }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
      new Response(null, { status: 204 }), // markRead
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    ];
    const spy = vi.fn().mockImplementation(() => {
      const next = responses.shift();
      return Promise.resolve(next ?? new Response(null, { status: 500 }));
    });
    global.fetch = spy as unknown as typeof fetch;

    const { result } = renderHook(() => useNotificationPoll());

    await vi.waitFor(() =>
      expect(result.current.unreadByDepartment.morning_briefing).toBe(1),
    );

    await act(async () => {
      await result.current.markRead("morning_briefing");
    });

    await vi.waitFor(() =>
      expect(result.current.unreadByDepartment.morning_briefing ?? 0).toBe(0),
    );
  });

  it("stops polling after a 401 and exposes error='unauthorized'", async () => {
    const spy = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 401 }));
    global.fetch = spy as unknown as typeof fetch;

    const { result } = renderHook(() => useNotificationPoll());

    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(result.current.error).toBe("unauthorized"));

    // Advance well past the poll interval; no more fetches must happen.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NOTIFICATION_POLL_MS * 3);
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });

  it("clears the timer on unmount and stops further fetches", async () => {
    const spy = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ total: 0, by_department: {} }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    global.fetch = spy as unknown as typeof fetch;

    const { unmount } = renderHook(() => useNotificationPoll());
    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1));

    unmount();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(NOTIFICATION_POLL_MS * 3);
    });
    expect(spy).toHaveBeenCalledTimes(1);
  });
});
