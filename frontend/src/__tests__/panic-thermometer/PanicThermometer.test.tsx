import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import PanicThermometer from "../../pages/departments/PanicThermometer";

vi.mock("../../hooks/usePtDashboard", () => ({
  usePtDashboard: () => ({
    data: {
      panels: {
        oil: {
          panel_id: "oil",
          status: "amber",
          label: "Above threshold",
          resolved_values: { price: 90, price_threshold: 85 },
          derived_scalars: {},
          extras: {},
          warnings: [],
        },
        inflation: {
          panel_id: "inflation",
          status: "green",
          label: "Anchored",
          resolved_values: { tip_price_latest: 100, tip_prev_close: 99 },
          derived_scalars: {},
          extras: {},
          warnings: [],
        },
        fed_language: {
          panel_id: "fed_language",
          status: "green",
          label: "Dovish",
          resolved_values: {},
          derived_scalars: {},
          extras: {},
          warnings: [],
        },
        wage_growth: {
          panel_id: "wage_growth",
          status: "green",
          label: "Normal",
          resolved_values: {},
          derived_scalars: {},
          extras: {},
          warnings: [],
        },
        diplomacy: {
          panel_id: "diplomacy",
          status: "green",
          label: "Within window",
          resolved_values: { window_days: 30 },
          derived_scalars: {},
          extras: {},
          warnings: [],
        },
      },
      composite: { level: "calm", score: 0, red_count: 0, mode: "count" },
      generated_at: "2026-04-25T12:00:00Z",
      warnings: [],
    },
    error: null,
    refresh: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../../hooks/usePtConfig", () => ({
  usePtConfig: () => ({
    config: {
      id: "u-1",
      panel_config: [],
      composite_settings: { mode: "count" },
      active_preset_id: null,
    },
    isLoading: false,
    error: null,
    save: vi.fn(),
    refresh: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock("../../hooks/usePtPresets", () => ({
  usePtPresets: () => ({
    presets: [],
    isLoading: false,
    error: null,
    refresh: vi.fn().mockResolvedValue(undefined),
    create: vi.fn(),
    rename: vi.fn(),
    remove: vi.fn(),
    apply: vi.fn().mockResolvedValue({}),
  }),
}));

describe("PanicThermometer page", () => {
  it("renders the five panel dashboards", () => {
    render(<PanicThermometer />);
    expect(screen.getByTestId("panel-dashboard-oil")).toBeInTheDocument();
    expect(screen.getByTestId("panel-dashboard-inflation")).toBeInTheDocument();
    expect(screen.getByTestId("panel-dashboard-fed_language")).toBeInTheDocument();
    expect(screen.getByTestId("panel-dashboard-wage_growth")).toBeInTheDocument();
    expect(screen.getByTestId("panel-dashboard-diplomacy")).toBeInTheDocument();
  });
});
