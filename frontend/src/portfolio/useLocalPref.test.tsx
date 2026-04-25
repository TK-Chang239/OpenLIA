import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, beforeEach } from "vitest";

import { useLocalPref } from "./useLocalPref";

describe("useLocalPref", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns the default when no value is stored", () => {
    const { result } = renderHook(() => useLocalPref("x", "list"));
    expect(result.current[0]).toBe("list");
  });

  it("persists writes to localStorage", () => {
    const { result } = renderHook(() =>
      useLocalPref<"list" | "grid">("portfolio:view", "list"),
    );
    act(() => result.current[1]("grid"));
    expect(window.localStorage.getItem("portfolio:view")).toBe("grid");
    expect(result.current[0]).toBe("grid");
  });

  it("hydrates from existing value", () => {
    window.localStorage.setItem("k", "stored");
    const { result } = renderHook(() => useLocalPref("k", "default"));
    expect(result.current[0]).toBe("stored");
  });
});
