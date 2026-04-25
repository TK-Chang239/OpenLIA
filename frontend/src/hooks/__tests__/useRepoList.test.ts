import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import React from "react";

const listRepoItemsFiltered = vi.fn();
vi.mock("../../api/repo", () => ({
  listRepoItemsFiltered: (...a: unknown[]) => listRepoItemsFiltered(...a),
}));

import { useRepoList } from "../useRepoList";

function wrapWith(initial: string) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return React.createElement(MemoryRouter, { initialEntries: [initial] }, children);
  };
}

const ROW = {
  id: "i1",
  report_id: "r1",
  department: "equity_research",
  title: "AAPL",
  filename: "AAPL.pdf",
  generated_at: "2026-04-20T10:00:00Z",
  saved_at: "2026-04-22T10:00:00Z",
};

describe("useRepoList", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    listRepoItemsFiltered.mockReset();
    listRepoItemsFiltered.mockResolvedValue({
      items: [ROW],
      page: 1,
      page_size: 50,
      has_more: false,
    });
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("fetches with default page_size 50 on mount", async () => {
    const { result } = renderHook(() => useRepoList(), { wrapper: wrapWith("/r") });
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    const arg = listRepoItemsFiltered.mock.calls[0][0];
    expect(arg.page).toBe(1);
    expect(arg.page_size).toBe(50);
    expect(result.current.rows).toHaveLength(1);
  });

  it("loadMore appends instead of replacing", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [ROW],
      page: 1,
      page_size: 50,
      has_more: true,
    });
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [{ ...ROW, id: "i2", report_id: "r2" }],
      page: 2,
      page_size: 50,
      has_more: false,
    });
    const { result } = renderHook(() => useRepoList(), { wrapper: wrapWith("/r") });
    await waitFor(() => expect(result.current.rows).toHaveLength(1));
    expect(result.current.hasMore).toBe(true);
    act(() => result.current.loadMore());
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    expect(result.current.rows.map((r) => r.id)).toEqual(["i1", "i2"]);
  });

  it("URL params round-trip into hook state", async () => {
    const { result } = renderHook(() => useRepoList(), {
      wrapper: wrapWith("/r?q=aapl&department=equity_research&sort=filename_asc"),
    });
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalled());
    expect(result.current.params.q).toBe("aapl");
    expect(result.current.params.departments).toEqual(["equity_research"]);
    expect(result.current.params.sort).toBe("filename_asc");
  });

  it("debounces q changes into a single fetch", async () => {
    const { result } = renderHook(() => useRepoList(), { wrapper: wrapWith("/r") });
    await waitFor(() => expect(listRepoItemsFiltered).toHaveBeenCalledTimes(1));
    listRepoItemsFiltered.mockClear();
    act(() => result.current.setParams({ q: "a" }));
    act(() => result.current.setParams({ q: "ap" }));
    act(() => result.current.setParams({ q: "app" }));
    // Advance past debounce.
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    await waitFor(() =>
      expect(
        listRepoItemsFiltered.mock.calls.filter((c) => c[0].q === "app").length,
      ).toBe(1),
    );
  });

  it("removeRow returns the row and removes it; restoreRow puts it back at index", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [ROW, { ...ROW, id: "i2", report_id: "r2", filename: "MSFT.pdf" }],
      page: 1,
      page_size: 50,
      has_more: false,
    });
    const { result } = renderHook(() => useRepoList(), { wrapper: wrapWith("/r") });
    await waitFor(() => expect(result.current.rows).toHaveLength(2));
    const target = result.current.rows[1];
    act(() => {
      result.current.removeRow("i2");
    });
    expect(result.current.rows).toHaveLength(1);
    act(() => {
      result.current.restoreRow(target, 1);
    });
    expect(result.current.rows.map((r) => r.id)).toEqual(["i1", "i2"]);
  });

  it("sentinelRef registers an IntersectionObserver and triggers loadMore on intersect", async () => {
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [ROW],
      page: 1,
      page_size: 50,
      has_more: true,
    });
    listRepoItemsFiltered.mockResolvedValueOnce({
      items: [{ ...ROW, id: "i2", report_id: "r2" }],
      page: 2,
      page_size: 50,
      has_more: false,
    });
    let cb: ((entries: { isIntersecting: boolean }[]) => void) | null = null;
    class FakeObserver {
      constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
        cb = callback;
      }
      observe(): void {}
      disconnect(): void {}
      unobserve(): void {}
    }
    const original = (globalThis as { IntersectionObserver?: unknown }).IntersectionObserver;
    (globalThis as { IntersectionObserver: unknown }).IntersectionObserver =
      FakeObserver as unknown as typeof IntersectionObserver;
    try {
      const { result } = renderHook(() => useRepoList(), { wrapper: wrapWith("/r") });
      await waitFor(() => expect(result.current.rows).toHaveLength(1));
      const node = document.createElement("div");
      act(() => result.current.sentinelRef(node));
      expect(cb).not.toBeNull();
      act(() => cb?.([{ isIntersecting: true }]));
      await waitFor(() => expect(result.current.rows).toHaveLength(2));
    } finally {
      (globalThis as { IntersectionObserver: unknown }).IntersectionObserver =
        original as typeof IntersectionObserver;
    }
  });

  it("clearFilters resets URL state", async () => {
    const { result } = renderHook(() => useRepoList(), {
      wrapper: wrapWith("/r?q=aapl&department=equity_research"),
    });
    await waitFor(() => expect(result.current.rows.length).toBeGreaterThanOrEqual(1));
    act(() => result.current.clearFilters());
    await waitFor(() => expect(result.current.params.q).toBe(""));
    expect(result.current.params.departments).toEqual([]);
  });
});
