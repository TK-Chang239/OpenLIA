import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as api from "../../api/panic-thermometer";
import PanicThermometer from "../../pages/departments/PanicThermometer";

function stubApi() {
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

  it("renders the topbar with severity pill and settings button", async () => {
    render(<PanicThermometer />);
    expect(screen.getAllByText("Panic Thermometer").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Severe · 3 of 5 red/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Open settings")).toBeInTheDocument();
  });

  it("renders all five scorecards with anchor hrefs", async () => {
    render(<PanicThermometer />);
    expect(screen.getByTestId("pt-scorecard-oil")).toHaveAttribute("href", "#oil");
    expect(screen.getByTestId("pt-scorecard-inflation")).toHaveAttribute("href", "#inflation");
    expect(screen.getByTestId("pt-scorecard-fed")).toHaveAttribute("href", "#fed");
    expect(screen.getByTestId("pt-scorecard-wage")).toHaveAttribute("href", "#wage");
    expect(screen.getByTestId("pt-scorecard-diplomacy")).toHaveAttribute("href", "#diplomacy");
  });

  it("renders Hero, all 5 deep-dive panels, releases table, and verdict", () => {
    render(<PanicThermometer />);
    expect(screen.getByText("Three of five indicators red.")).toBeInTheDocument();
    expect(screen.getByText("D1 · Oil price duration")).toBeInTheDocument();
    expect(screen.getByText("D2 · Inflation expectations")).toBeInTheDocument();
    expect(screen.getByText("D3 · Fed language tracker")).toBeInTheDocument();
    expect(screen.getByText("D4 · Wage growth")).toBeInTheDocument();
    expect(screen.getByText("D5 · Diplomatic progress")).toBeInTheDocument();
    expect(screen.getByText("Macro releases · last 7 days")).toBeInTheDocument();
    expect(screen.getByText("LIA · verdict")).toBeInTheDocument();
  });

  it("opens the settings drawer when Settings is clicked", async () => {
    render(<PanicThermometer />);
    fireEvent.click(screen.getByLabelText("Open settings"));
    await waitFor(() => {
      expect(screen.getByRole("dialog")).toBeInTheDocument();
    });
  });
});
