import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";

vi.mock("../api/settings", () => ({ getPrefs: vi.fn() }));
vi.mock("./index", () => ({ setUiLanguage: vi.fn() }));

import { getPrefs } from "../api/settings";
import { setUiLanguage } from "./index";
import { useUiLanguageSync } from "./useUiLanguage";

const getPrefsMock = vi.mocked(getPrefs);
const setUiLanguageMock = vi.mocked(setUiLanguage);

describe("useUiLanguageSync", () => {
  beforeEach(() => {
    getPrefsMock.mockReset();
    setUiLanguageMock.mockReset();
    getPrefsMock.mockResolvedValue({ display_language: "en" } as never);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("does not fetch prefs while unauthenticated", () => {
    renderHook(() => useUiLanguageSync(false, ""));
    expect(getPrefsMock).not.toHaveBeenCalled();
  });

  it("applies the user's language once authenticated", async () => {
    getPrefsMock.mockResolvedValue({ display_language: "zh-TW" } as never);
    renderHook(() => useUiLanguageSync(true, "u1"));
    await waitFor(() => expect(setUiLanguageMock).toHaveBeenCalledWith("zh-TW"));
  });

  it("re-syncs when auth flips to authenticated (SPA login regression)", async () => {
    const { rerender } = renderHook(
      ({ ready, key }) => useUiLanguageSync(ready, key),
      { initialProps: { ready: false, key: "" } },
    );
    expect(getPrefsMock).not.toHaveBeenCalled();
    rerender({ ready: true, key: "u1" });
    await waitFor(() => expect(setUiLanguageMock).toHaveBeenCalledWith("en"));
  });

  it("re-syncs when the signed-in user changes", async () => {
    const { rerender } = renderHook(
      ({ ready, key }) => useUiLanguageSync(ready, key),
      { initialProps: { ready: true, key: "u1" } },
    );
    await waitFor(() => expect(getPrefsMock).toHaveBeenCalledTimes(1));
    rerender({ ready: true, key: "u2" });
    await waitFor(() => expect(getPrefsMock).toHaveBeenCalledTimes(2));
  });
});
