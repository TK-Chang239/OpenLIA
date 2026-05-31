import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import * as settingsApi from "../../../api/settings";
import * as euApi from "../../../api/earnings-update";
import { ReportSettingsModal } from "../ReportSettingsModal";

vi.mock("../../../hooks/useEuDataSources", () => ({
  useEuDataSources: vi.fn(),
}));
import { useEuDataSources } from "../../../hooks/useEuDataSources";

const base: euApi.EuSettings = {
  provider_kind: "anthropic", model: "claude-sonnet-4-6", template_id: "eu_default",
  language: "en", length: "normal", reasoning_effort: null,
  financial_enabled: true, calendar_enabled: true, web_search_enabled: false,
};

const AVAILABLE = { available: true, provider_label: "EODHD", unavailable_reason: null };
const WS_OK = { available: true, provider_label: "claude-sonnet-4-6", unavailable_reason: null };
const WS_OFF = { available: false, provider_label: null, unavailable_reason: "model_no_web_search" };
const FIN_OFF = { available: false, provider_label: null, unavailable_reason: "eodhd_unconfigured" };

function mockDataSources(over: Record<string, unknown> = {}) {
  (useEuDataSources as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
    dataSources: {
      financial: AVAILABLE,
      earnings_calendar: AVAILABLE,
      web_search: WS_OK,
      other_connectors: [],
      ...over,
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
  });
}

beforeEach(() => {
  mockDataSources();
});

afterEach(() => {
  vi.restoreAllMocks();
});

function renderModal(onSave = vi.fn().mockResolvedValue(base)) {
  vi.spyOn(settingsApi, "getEnabledModels").mockResolvedValue([
    { id: "m1", provider_kind: "anthropic", model_ref: "claude-sonnet-4-6", display_name: "Claude Sonnet 4.6", is_enabled: true } as never,
  ]);
  vi.spyOn(euApi, "fetchTemplates").mockResolvedValue({ templates: [{ id: "eu_default", name: "Earnings Update (Default)", is_builtin: true, created_at: "", updated_at: "" }] });
  return { onSave, ...render(<ReportSettingsModal settings={base} onSave={onSave} onClose={() => {}} />) };
}

describe("ReportSettingsModal (v2)", () => {
  it("renders connector toggles and saves changes", async () => {
    const onSave = vi.fn().mockResolvedValue(base);
    renderModal(onSave);
    // toggle web search on (label now reads "Web search · via ...")
    const webSearch = await screen.findByTestId("eu-v2-connector-web_search");
    fireEvent.click(webSearch);
    fireEvent.click(screen.getByTestId("eu-v2-settings-save"));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ web_search_enabled: true })));
  });

  it("does not render section toggles or custom sections", () => {
    render(<ReportSettingsModal settings={base} onSave={vi.fn()} onClose={() => {}} />);
    expect(screen.queryByText(/custom section/i)).toBeNull();
  });

  it("renders available financial slot with provider label and an enabled toggle", () => {
    mockDataSources();
    renderModal();
    const tog = screen.getByTestId("eu-v2-connector-financial");
    expect(tog).not.toBeDisabled();
    expect(tog).toHaveAttribute("aria-label", expect.stringMatching(/EODHD/));
  });

  it("disables an unavailable web-search slot and shows its reason", () => {
    mockDataSources({ web_search: WS_OFF });
    renderModal();
    expect(screen.getByTestId("eu-v2-connector-web_search")).toBeDisabled();
    expect(screen.getByText(/does not support web search/i)).toBeInTheDocument();
  });

  it("shows the empty state when all slots are unavailable", () => {
    mockDataSources({ financial: FIN_OFF, earnings_calendar: FIN_OFF, web_search: WS_OFF });
    renderModal();
    expect(screen.getByTestId("eu-v2-data-sources-empty")).toBeInTheDocument();
  });

  it("shows the muted footnote listing other configured connectors", () => {
    mockDataSources({ other_connectors: [{ display_name: "FMP", category: "financial" }] });
    renderModal();
    expect(screen.getByTestId("eu-v2-data-sources-other")).toHaveTextContent("FMP");
  });
});
