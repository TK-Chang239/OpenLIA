import { describe, expect, test } from "vitest";
import { renderHook } from "@testing-library/react";

import { useOmEntranceChoreography } from "../EquityResearchV3";

describe("om-anim entrance opt-in", () => {
  test("adds om-anim/data-om-auto on mount and removes them on unmount", () => {
    const { unmount } = renderHook(() => useOmEntranceChoreography());
    expect(document.documentElement.classList.contains("om-anim")).toBe(true);
    expect(document.body.hasAttribute("data-om-auto")).toBe(true);
    unmount();
    expect(document.documentElement.classList.contains("om-anim")).toBe(false);
    expect(document.body.hasAttribute("data-om-auto")).toBe(false);
  });
});
