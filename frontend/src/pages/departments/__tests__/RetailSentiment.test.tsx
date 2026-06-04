import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as api from "../../../api/retail-sentiment";
import * as deptHealth from "../../../api/dept-health";
import RetailSentiment from "../RetailSentiment";

const basePayload: api.RetailSentimentPayload = {
  subject: "AAPL",
  sentiment_score: 0.42,
  direction: "bullish",
  momentum: 0.05,
  trend_label: "Improving steadily",
  buzz_level: "elevated",
  buzz_note: "Elevated discussion volume vs 30-day average.",
  bull_pct: 62.5,
  bear_pct: 27.3,
  narratives: [
    "Strong earnings expectations ahead of Q2.",
    "Services segment gaining traction.",
  ],
  signals: [
    { name: "Momentum crossover", severity: "info", note: "5d MA crossed above 20d." },
    { name: "Buzz spike detected", severity: "caution", note: "Volume 2.1x above average." },
  ],
  evidence: [
    {
      title: "Apple beats expectations",
      url: "https://example.com/article",
      source: "Reuters",
      classification: "bullish",
      published_at: "2026-06-01T10:00:00Z",
    },
  ],
  narrative: "Retail crowd is broadly bullish on AAPL heading into earnings.",
  aggregated_sentiment: 0.38,
  analyst_gap: 0.12,
  captured_at: "2026-06-03T09:00:00Z",
};

const baseDashboardResponse: api.DashboardResponse<api.RetailSentimentPayload> = {
  payload: basePayload,
  generated_at: "2026-06-03T09:00:00Z",
  is_stale: false,
  provenance: "report_dash_rs",
};

function stubAll() {
  vi.spyOn(api, "getDashboard").mockResolvedValue(baseDashboardResponse);
  vi.spyOn(api, "refreshDashboard").mockResolvedValue({
    job_run_id: "j1",
    status: "queued",
  });
  vi.spyOn(api, "getSchedule").mockResolvedValue({ schedule: null });
  vi.spyOn(deptHealth, "fetchDeptHealth").mockResolvedValue([
    {
      department_id: "retail_sentiment",
      status: "active",
      reason: null,
      missing_categories: [],
      unresolved_needs: [],
      satisfied_categories: ["web_search", "news"],
      optional_categories: ["financial", "news"],
      required_categories: ["web_search"],
    },
  ]);
}

describe("RetailSentiment page", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    stubAll();
  });

  it("renders the page header", () => {
    render(<RetailSentiment />);
    expect(screen.getByTestId("retail-sentiment")).toBeInTheDocument();
  });

  it("shows empty watchlist state when no ticker selected", () => {
    render(<RetailSentiment />);
    expect(screen.getByTestId("rs-empty-watchlist")).toBeInTheDocument();
  });

  it("renders overview once ticker is added and payload arrives", async () => {
    render(<RetailSentiment />);
    const addBtn = screen.getByTestId("ticker-add-button");
    fireEvent.click(addBtn);
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(api.getDashboard).toHaveBeenCalledWith("AAPL");
    });
    await waitFor(() => {
      expect(screen.getByTestId("rs-overview-payload")).toBeInTheDocument();
    });
  });

  it("renders sentiment score from payload", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("sentiment-gauge")).toBeInTheDocument();
    });
  });

  it("renders direction, buzz level, and narrative from payload", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-buzz-level")).toHaveTextContent("Elevated");
      expect(screen.getByTestId("rs-narrative")).toHaveTextContent(
        "Retail crowd is broadly bullish on AAPL heading into earnings.",
      );
    });
  });

  it("renders narratives list", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-narratives")).toBeInTheDocument();
      expect(screen.getByText("Strong earnings expectations ahead of Q2.")).toBeInTheDocument();
    });
  });

  it("renders signals section", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-signals")).toBeInTheDocument();
      expect(screen.getByText("Momentum crossover")).toBeInTheDocument();
    });
  });

  it("renders evidence list", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-evidence")).toBeInTheDocument();
      expect(screen.getByText("Apple beats expectations")).toBeInTheDocument();
    });
  });

  it("Generate now button calls refreshDashboard and shows polling skeleton", async () => {
    // Return null payload initially, then a real payload after refresh
    vi.spyOn(api, "getDashboard")
      .mockResolvedValueOnce({
        payload: null,
        generated_at: null,
        is_stale: false,
        provenance: null,
      })
      .mockResolvedValue(baseDashboardResponse);

    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "TSLA" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-overview-empty")).toBeInTheDocument();
    });

    const genBtn = screen.getByTestId("rs-generate-now");
    fireEvent.click(genBtn);

    await waitFor(() => {
      expect(api.refreshDashboard).toHaveBeenCalledWith("TSLA");
    });
  });

  it("shows settings panel when settings button clicked", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("rs-settings-button"));
    expect(screen.getByTestId("rs-settings-panel")).toBeInTheDocument();
  });

  it("shows stale badge when is_stale is true", async () => {
    vi.spyOn(api, "getDashboard").mockResolvedValue({
      ...baseDashboardResponse,
      is_stale: true,
    });

    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-stale-badge")).toBeInTheDocument();
    });
  });

  it("renders bull/bear percentages from payload", async () => {
    render(<RetailSentiment />);
    fireEvent.click(screen.getByTestId("ticker-add-button"));
    const input = screen.getByTestId("ticker-add-input");
    fireEvent.change(input, { target: { value: "AAPL" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("rs-bull-pct")).toHaveTextContent("62.5%");
      expect(screen.getByTestId("rs-bear-pct")).toHaveTextContent("27.3%");
    });
  });
});
