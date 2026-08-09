import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/panic-thermometer";
import type { DashboardPayload, PanelResult } from "../../api/panic-thermometer";
import PanicThermometer from "../../pages/departments/PanicThermometer";

function panel(over: Partial<PanelResult> & Pick<PanelResult, "panel_id">): PanelResult {
  return {
    status: "green",
    label: "",
    resolved_values: {},
    derived_scalars: {},
    extras: {},
    raw_series: {},
    params: {},
    warnings: [],
    ...over,
  };
}

function dashboard(): DashboardPayload {
  return {
    composite: { level: "severe", score: 3.2, red_count: 3, mode: "count" },
    generated_at: "2026-05-04T10:48:00Z",
    warnings: [],
    panels: {
      oil: panel({
        panel_id: "oil",
        status: "red",
        resolved_values: { streak_days: 47, price: 48.2 },
        raw_series: { price: [40, 42, 44, 46, 48.2], high: [], low: [] },
        params: {
          ticker: "BNO.US",
          price_threshold: 45,
          streak_amber: 1,
          streak_red: 30,
          streak_dark_red: 90,
        },
      }),
      inflation: panel({
        panel_id: "inflation",
        status: "amber",
        extras: { michigan_5y: 2.9, michigan_prev: 2.7, michigan_5y_missing: false },
        raw_series: { tip_price: [108, 110, 112], price: [] },
        params: { level_amber: 2.5, level_red: 3.0, level_dark_red: 3.5 },
      }),
      fed_language: panel({
        panel_id: "fed_language",
        status: "red",
        extras: {
          hawkish_keyword_detected: true,
          matched_phrase: "persistent inflation",
          matched_headline: "Powell sees persistent inflation",
          matched_date: "30 Apr",
          days_since_fomc: 4,
        },
        params: {
          news_lookback_days: 30,
          hawkish_keywords: ["persistent inflation"],
          dovish_keywords: ["patient"],
          neutral_keywords: ["data dependent"],
          crisis_keywords: ["unanchored"],
        },
      }),
      wage_growth: panel({
        panel_id: "wage_growth",
        status: "dark_red",
        extras: { value: 0.6, prev_value: 0.6, consecutive_count: 2, avg_12m: 0.38 },
        raw_series: { value: [0.2, 0.3, 0.4, 0.5, 0.6, 0.6] },
        params: {
          wage_threshold_amber: 0.4,
          wage_threshold_red: 0.5,
          consecutive_required: 2,
        },
      }),
      diplomacy: panel({
        panel_id: "diplomacy",
        status: "amber",
        extras: {
          days_elapsed: 22,
          days_remaining: 8,
          progress_detected: true,
          escalation_detected: false,
          matched_progress_headlines: ["Riyadh hosts de-escalation talks"],
          matched_escalation_headlines: [],
        },
        params: { window_days: 30, window_amber_pct: 50 },
      }),
    },
  };
}

function stubApi() {
  vi.spyOn(api, "fetchDashboard").mockResolvedValue(dashboard());
  vi.spyOn(api, "fetchConfig").mockResolvedValue({
    id: "u1",
    panel_config: [
      {
        panel_id: "oil",
        rules: [],
        params: {},
        streak_condition: null,
        manual_override: null,
        milestone_date: null,
      },
    ],
    composite_settings: { mode: "count" },
    active_preset_id: null,
  });
  vi.spyOn(api, "listPresets").mockResolvedValue([]);
}

describe("PanicThermometer page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubApi();
  });

  it("renders the topbar severity pill from the live composite", async () => {
    render(<PanicThermometer />);
    expect(screen.getAllByText("Panic Thermometer").length).toBeGreaterThan(0);
    // Computed pill: severity label + red/total from composite.
    await waitFor(() =>
      expect(screen.getAllByText(/Severe/).length).toBeGreaterThan(0),
    );
    expect(screen.getAllByText(/3 of 5 red/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Open settings")).toBeInTheDocument();
  });

  it("renders all five scorecards with anchor hrefs", async () => {
    render(<PanicThermometer />);
    await waitFor(() =>
      expect(screen.getByTestId("pt-scorecard-oil")).toHaveAttribute("href", "#oil"),
    );
    expect(screen.getByTestId("pt-scorecard-inflation")).toHaveAttribute("href", "#inflation");
    expect(screen.getByTestId("pt-scorecard-fed")).toHaveAttribute("href", "#fed");
    expect(screen.getByTestId("pt-scorecard-wage")).toHaveAttribute("href", "#wage");
    expect(screen.getByTestId("pt-scorecard-diplomacy")).toHaveAttribute("href", "#diplomacy");
  });

  it("renders Hero, all 5 deep-dive panels, and the verdict (no releases table)", async () => {
    render(<PanicThermometer />);
    // Computed hero headline from the live red_count.
    await waitFor(() =>
      expect(screen.getByText("3 of 5 panels red.")).toBeInTheDocument(),
    );
    expect(screen.getByText("D1 · Oil price duration")).toBeInTheDocument();
    expect(screen.getByText("D2 · Inflation expectations")).toBeInTheDocument();
    expect(screen.getByText("D3 · Fed language tracker")).toBeInTheDocument();
    expect(screen.getByText("D4 · Wage growth")).toBeInTheDocument();
    expect(screen.getByText("D5 · Diplomatic progress")).toBeInTheDocument();
    expect(screen.getByText("LIA · verdict")).toBeInTheDocument();
    // Releases table has been dropped.
    expect(screen.queryByText("Macro releases · last 7 days")).not.toBeInTheDocument();
  });

  it("shows an error state with a Retry button when the dashboard fails", async () => {
    vi.spyOn(api, "fetchDashboard").mockRejectedValue(new Error("boom"));
    render(<PanicThermometer />);
    await waitFor(() =>
      expect(screen.getByText("Could not load the dashboard")).toBeInTheDocument(),
    );
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });

  it("shows the empty state when every panel is unavailable", async () => {
    const empty = dashboard();
    for (const p of Object.values(empty.panels)) {
      p.status = "disabled";
      p.warnings = ["EODHD connector required"];
    }
    vi.spyOn(api, "fetchDashboard").mockResolvedValue(empty);
    render(<PanicThermometer />);
    await waitFor(() =>
      expect(
        screen.getByText("Connect EODHD to activate this dashboard"),
      ).toBeInTheDocument(),
    );
  });

  it("opens the settings drawer when Settings is clicked", async () => {
    render(<PanicThermometer />);
    await waitFor(() =>
      expect(screen.getByText("D1 · Oil price duration")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByLabelText("Open settings"));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });
});
