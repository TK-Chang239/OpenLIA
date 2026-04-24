import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { useTheme } from "./useTheme";

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
  });

  it("defaults to light and sets data-theme attribute", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("toggles to dark and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("openlia:theme")).toBe("dark");
  });

  it("hydrates from localStorage on mount", () => {
    localStorage.setItem("openlia:theme", "dark");
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("dark");
  });
});
