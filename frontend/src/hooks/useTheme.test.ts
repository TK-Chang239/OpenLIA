import { act, renderHook } from "@testing-library/react";
import { describe, it, expect, beforeEach } from "vitest";
import { setThemeSetting, useTheme } from "./useTheme";

describe("useTheme", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    // Module store survives between tests; reset it explicitly.
    setThemeSetting("system");
    localStorage.clear();
  });

  it("defaults to system, resolving light without an OS dark preference", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    expect(result.current.resolved).toBe("light");
  });

  it("sets dark, applies data-theme, and persists", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    expect(result.current.theme).toBe("dark");
    expect(result.current.resolved).toBe("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    expect(localStorage.getItem("openlia:theme")).toBe("dark");
  });

  it("persists an explicit system choice", () => {
    const { result } = renderHook(() => useTheme());
    act(() => result.current.setTheme("dark"));
    act(() => result.current.setTheme("system"));
    expect(localStorage.getItem("openlia:theme")).toBe("system");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
  });

  it("shares one store across hook instances", () => {
    const a = renderHook(() => useTheme());
    const b = renderHook(() => useTheme());
    act(() => a.result.current.setTheme("dark"));
    expect(b.result.current.theme).toBe("dark");
  });
});
