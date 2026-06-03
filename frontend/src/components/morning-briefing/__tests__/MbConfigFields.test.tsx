import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/morning-briefing";
import * as settingsApi from "../../../api/settings";
import {
  MbConfigFields,
  isBriefEmpty,
  type MbConfigDraft,
} from "../MbConfigFields";

function draft(over: Partial<MbConfigDraft> = {}): MbConfigDraft {
  return {
    template_id: "mb_default",
    instructions_id: null,
    provider_ids: [],
    web_search: false,
    provider_kind: null,
    model: null,
    language: "en",
    length: "normal",
    reasoning_effort: null,
    ...over,
  };
}

describe("MbConfigFields", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(api, "listMbTemplates").mockResolvedValue({ templates: [] });
    vi.spyOn(api, "listMbInstructions").mockResolvedValue([]);
    vi.spyOn(api, "getMbDataSources").mockResolvedValue({ sources: [] });
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
  });

  it("renders the config controls", async () => {
    render(<MbConfigFields draft={draft()} onChange={vi.fn()} />);
    expect(await screen.findByTestId("mb-template-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-instructions-select")).toBeInTheDocument();
    expect(screen.getByTestId("mb-language-select")).toBeInTheDocument();
  });

  it("does NOT render scheduling fields", async () => {
    render(<MbConfigFields draft={draft()} onChange={vi.fn()} />);
    await screen.findByTestId("mb-template-select");
    expect(screen.queryByTestId("mb-schedule-time")).not.toBeInTheDocument();
  });

  it("isBriefEmpty is true only for freeform + no instructions", () => {
    expect(isBriefEmpty(draft({ template_id: "freeform", instructions_id: null }))).toBe(true);
    expect(isBriefEmpty(draft({ template_id: "freeform", instructions_id: "i1" }))).toBe(false);
    expect(isBriefEmpty(draft({ template_id: "mb_default", instructions_id: null }))).toBe(false);
  });
});
