import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/retail-sentiment";
import RetailSentiment from "../RetailSentiment";

const baseConfig = {
  id: "c1",
  user_id: "u1",
  active_tab: "overview",
  metric_settings: {},
  filter_presets: [],
  refresh_interval_minutes: 60,
};

const baseDashboard = {
  tickers: ["AAPL"],
  snapshots: [
    {
      ticker: "AAPL",
      captured_at: new Date().toISOString(),
      sentiment_score: 0.4,
      buzz_volume: 1.5,
      buzz_count: 12,
      sentiment_momentum: 0.1,
      bull_bear_ratio: 2.0,
      buzz_sentiment_divergence: 0.3,
      social_velocity: 0.5,
      cross_source_agreement: 0.8,
      put_call_ratio: null,
      short_interest_pressure: null,
      narrative_concentration: null,
      institutional_retail_gap: null,
      event_sensitivity: null,
      source_breakdown: {},
      narrative: "Solid bullish flow.",
    },
  ],
  generated_at: new Date().toISOString(),
};

function stubAll() {
  vi.spyOn(api, "getDashboard").mockResolvedValue(baseDashboard);
  vi.spyOn(api, "getSpikes").mockResolvedValue({ spikes: [] });
  vi.spyOn(api, "getConfig").mockResolvedValue(baseConfig);
  vi.spyOn(api, "getSchedule").mockResolvedValue({ schedule: null });
  vi.spyOn(api, "getHistory").mockResolvedValue({
    ticker: "AAPL",
    snapshots: baseDashboard.snapshots,
  });
  vi.spyOn(api, "updateConfig").mockResolvedValue(baseConfig);
}

describe("RetailSentiment page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubAll();
  });

  it("renders 3 spec tabs (Overview / Evidence / Insights)", async () => {
    render(<RetailSentiment />);
    await waitFor(() => {
      expect(screen.getByTestId("tab-overview")).toBeInTheDocument();
      expect(screen.getByTestId("tab-evidence")).toBeInTheDocument();
      expect(screen.getByTestId("tab-insights")).toBeInTheDocument();
    });
  });

  it("opens metrics deep dive when ? button clicked", async () => {
    render(<RetailSentiment />);
    fireEvent.click(
      await screen.findByLabelText(/Open metrics deep dive/i),
    );
    expect(screen.getByTestId("metrics-deep-dive")).toBeInTheDocument();
  });

  it("opens settings drawer when Settings clicked", async () => {
    render(<RetailSentiment />);
    fireEvent.click(await screen.findByText("Settings"));
    expect(screen.getByTestId("settings-drawer")).toBeInTheDocument();
  });

  it("switches to evidence tab and persists via PUT /config", async () => {
    render(<RetailSentiment />);
    const upd = vi.mocked(api.updateConfig);
    fireEvent.click(await screen.findByTestId("tab-evidence"));
    await waitFor(() => {
      expect(upd).toHaveBeenCalledWith({ active_tab: "evidence" });
    });
  });

  it("manual run trigger calls runSnapshot for selected tickers", async () => {
    const run = vi.spyOn(api, "runSnapshot").mockResolvedValue({
      snapshots: [],
    });
    render(<RetailSentiment />);
    // Wait for the dashboard load (so AAPL is in tickers state).
    await screen.findByText(/Retail Sentiment/);
    await waitFor(() => {
      // tickers gets seeded from dashboard.
      expect(
        screen.queryByTestId("ticker-pill-AAPL"),
      ).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText("Run snapshot"));
    await waitFor(() => {
      expect(run).toHaveBeenCalledWith(["AAPL"]);
    });
  });

  it("shows error banner when run fails", async () => {
    vi.spyOn(api, "runSnapshot").mockRejectedValue(new Error("boom"));
    render(<RetailSentiment />);
    await waitFor(() =>
      expect(screen.queryByTestId("ticker-pill-AAPL")).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Run snapshot"));
    await waitFor(() => {
      expect(screen.getByTestId("rs-error-banner")).toHaveTextContent(/boom/);
    });
  });

  it("renders empty-watchlist state when there are no tickers", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      tickers: [],
      snapshots: [],
      generated_at: new Date().toISOString(),
    });
    render(<RetailSentiment />);
    await waitFor(() => {
      expect(screen.getByTestId("rs-empty")).toBeInTheDocument();
    });
  });

  it("Import-from-Portfolio button is wired (shows pending message)", async () => {
    render(<RetailSentiment />);
    fireEvent.click(await screen.findByText(/Import from Portfolio/i));
    await waitFor(() => {
      expect(screen.getByTestId("rs-error-banner")).toHaveTextContent(
        /Portfolio import/i,
      );
    });
  });
});
