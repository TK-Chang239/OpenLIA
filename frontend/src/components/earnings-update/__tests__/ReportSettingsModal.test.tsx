import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as settingsApi from "../../../api/settings";
import * as euApi from "../../../api/earnings-update";
import { ReportSettingsModal } from "../ReportSettingsModal";

const base: euApi.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ReportSettingsModal (v2)", () => {
  it("renders connector toggles and saves changes", async () => {
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([
      { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
    ]);
    vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [{ id: "eu_default", name: "Earnings Update (Default)", is_builtin: true, created_at: "", updated_at: "" }] });
    const onSave = vi.fn().mockResolvedValue(base);
    render(<ReportSettingsModal settings={base} onSave={onSave} onClose={() => {}} />);
    // toggle web search on
    const webSearch = await screen.findByTestId("eu-v2-connector-web_search");
    fireEvent.click(webSearch);
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ web_search_enabled: true })));
  });

  it("does not render section toggles or custom sections", () => {
    vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([]);
    vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [] });
    render(<ReportSettingsModal settings={base} onSave={vi.fn()} onClose={() => {}} />);
    expect(screen.queryByText(/custom section/i)).toBeNull();
  });
});
