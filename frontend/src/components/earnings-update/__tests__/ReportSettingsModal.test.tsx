import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as settingsApi from "../../../api/settings";
import * as euApi from "../../../api/earnings-update";
import type { DataSource } from "../../../api/earnings-update";
import { ReportSettingsModal } from "../ReportSettingsModal";

vi.mock("../../../hooks/useEuDataSources", () => ({
  useEuDataSources: vi.fn(),
}));
import { useEuDataSources } from "../../../hooks/useEuDataSources";

const base: euApi.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  enabled_provider_ids: ["eodhd"], web_search_enabled: false,
  instructions_id: null, batch_enabled: false,
};

const EODHD: DataSource = {
  key: "eodhd", display_name: "EODHD", category: "financial",
  routing: "curated", available: true, enabled: true, unavailable_reason: null,
};
const NEWSAPI: DataSource = {
  key: "newsapi_ai", display_name: "NewsAPI.ai", category: "news",
  routing: "dispatcher", available: true, enabled: false, unavailable_reason: null,
};
const WS_OFF: DataSource = {
  key: "model_web_search", display_name: "Web search", category: "web_search",
  routing: "model_native", available: false, enabled: false,
  unavailable_reason: "model_no_web_search",
};
const WS_OK: DataSource = { ...WS_OFF, available: true, unavailable_reason: null };

function mockSources(sources: DataSource[]) {
  (useEuDataSources as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    sources,
    loading: false,
    error: null,
    refresh: vi.fn(),
  });
}

beforeEach(() => {
  mockSources([EODHD, NEWSAPI, WS_OK]);
  vi.spyOn(euApi, "listEuInstructions").mockResolvedValue([]);
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderModal(onSave = vi.fn().mockResolvedValue(base), settings = base) {
  vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([
    { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
  ]);
  vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [{ id: "eu_default", name: "Earnings Update (Default)", is_builtin: true, created_at: "", updated_at: "" }] });
  vi.spyOn(euApi, "listEuInstructions").mockResolvedValue([]);
  return { onSave, ...render(<ReportSettingsModal settings={settings} onSave={onSave} onClose={() => {}} />) };
}

describe("ReportSettingsModal (v2)", () => {
  it("renders one toggle per source", () => {
    renderModal();
    expect(screen.getByTestId("eu-v2-connector-eodhd")).toBeInTheDocument();
    expect(screen.getByTestId("eu-v2-connector-newsapi_ai")).toBeInTheDocument();
    expect(screen.getByTestId("eu-v2-connector-model_web_search")).toBeInTheDocument();
  });

  it("reflects enabled state from draft.enabled_provider_ids", () => {
    renderModal();
    expect(screen.getByTestId("eu-v2-connector-eodhd")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("eu-v2-connector-newsapi_ai")).toHaveAttribute("aria-checked", "false");
  });

  it("toggling a registry source adds its key to enabled_provider_ids on save", async () => {
    const onSave = vi.fn().mockResolvedValue(base);
    renderModal(onSave);
    fireEvent.click(screen.getByTestId("eu-v2-connector-newsapi_ai"));
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          enabled_provider_ids: expect.arrayContaining(["eodhd", "newsapi_ai"]),
        }),
      ),
    );
  });

  it("toggling the model-web-search source flips web_search_enabled on save", async () => {
    const onSave = vi.fn().mockResolvedValue(base);
    renderModal(onSave);
    fireEvent.click(screen.getByTestId("eu-v2-connector-model_web_search"));
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ web_search_enabled: true }),
      ),
    );
  });

  it("toggling batch mode flips batch_enabled on save", async () => {
    const onSave = vi.fn().mockResolvedValue(base);
    renderModal(onSave);
    fireEvent.click(screen.getByTestId("eu-v2-batch-enabled"));
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ batch_enabled: true }),
      ),
    );
  });

  it("disables the batch toggle for an unsupported provider", () => {
    renderModal(vi.fn().mockResolvedValue(base), {
      ...base,
      provider_kind: "ollama",
      model: "llama3",
    });
    expect(screen.getByTestId("eu-v2-batch-enabled")).toBeDisabled();
    expect(
      screen.getByText(/requires an OpenAI or Anthropic model/i),
    ).toBeInTheDocument();
  });

  it("disables an unavailable web-search source and shows its reason", () => {
    mockSources([EODHD, WS_OFF]);
    renderModal();
    expect(screen.getByTestId("eu-v2-connector-model_web_search")).toBeDisabled();
    expect(screen.getByText(/does not support web search/i)).toBeInTheDocument();
  });

  it("does not render the old 'also configured' footnote", () => {
    renderModal();
    expect(screen.queryByTestId("eu-v2-data-sources-other")).toBeNull();
  });

  it("does not render section toggles or custom sections", () => {
    renderModal();
    expect(screen.queryByText(/custom section/i)).toBeNull();
  });

  it("disables Save and shows error when freeform template and no instructions", async () => {
    renderModal();
    const select = await screen.findByTestId("eu-v2-template-select");
    fireEvent.change(select, { target: { value: "freeform" } });
    expect(screen.getByTestId("eu-v2-settings-save")).toBeDisabled();
    expect(screen.getByText(/at least one is required/i)).toBeInTheDocument();
  });

  it("keeps Save enabled for a normal template with no instructions", async () => {
    renderModal();
    const select = await screen.findByTestId("eu-v2-template-select");
    fireEvent.change(select, { target: { value: "eu_default" } });
    expect(screen.getByTestId("eu-v2-settings-save")).not.toBeDisabled();
    expect(screen.queryByText(/at least one is required/i)).toBeNull();
  });
});
