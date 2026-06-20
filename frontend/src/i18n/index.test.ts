import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { detectInitialLanguage } from "./index";

const STORAGE_KEY = "openlia.displayLanguage";

function setNavigatorLanguage(value: string): void {
  Object.defineProperty(window.navigator, "language", {
    value,
    configurable: true,
  });
}

describe("detectInitialLanguage", () => {
  let originalLanguage: string;

  beforeEach(() => {
    originalLanguage = window.navigator.language;
    window.localStorage.clear();
  });

  afterEach(() => {
    setNavigatorLanguage(originalLanguage);
    window.localStorage.clear();
  });

  it("defaults to English when no choice is stored, ignoring a Chinese browser", () => {
    setNavigatorLanguage("zh-TW");
    expect(detectInitialLanguage()).toBe("en");
  });

  it("honors an explicit stored zh-TW choice", () => {
    window.localStorage.setItem(STORAGE_KEY, "zh-TW");
    expect(detectInitialLanguage()).toBe("zh-TW");
  });

  it("honors an explicit stored en choice", () => {
    setNavigatorLanguage("zh-TW");
    window.localStorage.setItem(STORAGE_KEY, "en");
    expect(detectInitialLanguage()).toBe("en");
  });
});
