import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useCollapsed, COLLAPSED_STORAGE_KEY } from "./useCollapsed";

describe("useCollapsed", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("defaults to false when storage is empty", () => {
    const { result } = renderHook(() => useCollapsed());
    expect(result.current[0]).toBe(false);
  });

  it("reads persisted value on mount", () => {
    window.localStorage.setItem(COLLAPSED_STORAGE_KEY, "true");
    const { result } = renderHook(() => useCollapsed());
    expect(result.current[0]).toBe(true);
  });

  it("persists value on toggle", () => {
    const { result } = renderHook(() => useCollapsed());
    act(() => result.current[1](true));
    expect(window.localStorage.getItem(COLLAPSED_STORAGE_KEY)).toBe("true");
    expect(result.current[0]).toBe(true);
  });

  it("tolerates localStorage throwing (private mode)", () => {
    const setItem = vi
      .spyOn(Storage.prototype, "setItem")
      .mockImplementation(() => {
        throw new Error("QuotaExceeded");
      });

    const { result } = renderHook(() => useCollapsed());
    act(() => result.current[1](true));
    expect(result.current[0]).toBe(true);
    expect(setItem).toHaveBeenCalled();
  });
});
