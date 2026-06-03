import { beforeEach, describe, expect, it } from "vitest";

import {
  RUN_NOW_LS_KEY,
  libraryDefaultDraft,
  loadRunNowDraft,
  saveRunNowDraft,
} from "../mbRunNowDraft";

describe("mbRunNowDraft", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("returns library defaults when nothing is stored", () => {
    expect(loadRunNowDraft()).toEqual(libraryDefaultDraft());
  });

  it("library default is a runnable (non-freeform) template", () => {
    expect(libraryDefaultDraft().template_id).toBe("mb_default");
  });

  it("round-trips a saved draft", () => {
    const draft = {
      ...libraryDefaultDraft(),
      template_id: "freeform",
      instructions_id: "ins-1",
      provider_ids: ["eodhd"],
      web_search: true,
      provider_kind: "anthropic",
      model: "claude-sonnet-4-6",
      language: "zh-Hant",
      length: "concise",
      reasoning_effort: "high" as const,
    };
    saveRunNowDraft(draft);
    expect(loadRunNowDraft()).toEqual(draft);
  });

  it("merges a partial stored config over the defaults", () => {
    window.localStorage.setItem(
      RUN_NOW_LS_KEY,
      JSON.stringify({ length: "elaborative" }),
    );
    expect(loadRunNowDraft()).toEqual({
      ...libraryDefaultDraft(),
      length: "elaborative",
    });
  });

  it("falls back to defaults on malformed JSON", () => {
    window.localStorage.setItem(RUN_NOW_LS_KEY, "not json{");
    expect(loadRunNowDraft()).toEqual(libraryDefaultDraft());
  });
});
