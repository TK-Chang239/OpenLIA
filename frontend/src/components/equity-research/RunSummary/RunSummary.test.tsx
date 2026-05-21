import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RunSummary } from "./RunSummary";
import type { RunSummaryData } from "./RunSummary";

const baseData: RunSummaryData = {
  engine_version: "2.2",
  template_id: "stock_initiation",
  template_name: "Stock Initiation",
  composer_inputs: {},
  outcomes: [
    { task_type: "gather", task_name: "Fetch price data", status: "OK", duration_ms: 120 },
    { task_type: "model", task_name: "Build DCF", status: "SKIPPED", notes: "no data", duration_ms: 0 },
    { task_type: "draft", task_name: "Write valuation", status: "DEGRADED", notes: "partial", duration_ms: 800 },
    { task_type: "verify", task_name: "Check citations", status: "FAILED", notes: "unresolved", duration_ms: 200 },
  ],
  unsupported_requests_dismissed: [],
  unsupported_requests_slipped: [],
  total_duration_ms: 1120,
  cache_stats: {},
};

describe("RunSummary", () => {
  it("renders all four status types with color classes", () => {
    const { container } = render(<RunSummary summary={baseData} />);

    expect(screen.getByText("OK")).toBeInTheDocument();
    expect(screen.getByText("SKIPPED")).toBeInTheDocument();
    expect(screen.getByText("DEGRADED")).toBeInTheDocument();
    expect(screen.getByText("FAILED")).toBeInTheDocument();

    const rows = container.querySelectorAll("table.run-summary-outcomes tbody tr");
    expect(rows[0].className).toContain("status-ok");
    expect(rows[1].className).toContain("status-skipped");
    expect(rows[2].className).toContain("status-degraded");
    expect(rows[3].className).toContain("status-failed");
  });

  it("shows unsupported_requests_dismissed list", () => {
    const data: RunSummaryData = {
      ...baseData,
      unsupported_requests_dismissed: ["devil's advocate"],
    };
    render(<RunSummary summary={data} />);
    expect(screen.getByText("devil's advocate")).toBeInTheDocument();
  });

  it("shows (none) when both lists empty", () => {
    render(<RunSummary summary={baseData} />);
    const nones = screen.getAllByText("(none)");
    expect(nones).toHaveLength(2);
  });

  it("displays engine version", () => {
    render(<RunSummary summary={baseData} />);
    expect(screen.getByText(/Engine v2\.2/)).toBeInTheDocument();
  });

  it("omits cache stats block when empty", () => {
    render(<RunSummary summary={baseData} />);
    expect(screen.queryByText("Cache stats")).toBeNull();
  });

  it("renders cache stats block when entries exist", () => {
    const data: RunSummaryData = {
      ...baseData,
      cache_stats: { eodhd: { hits: 3, misses: 1 } },
    };
    render(<RunSummary summary={data} />);
    expect(screen.getByText("Cache stats")).toBeInTheDocument();
    expect(screen.getByText("eodhd")).toBeInTheDocument();
  });

  it("shows total duration in header line", () => {
    render(<RunSummary summary={baseData} />);
    expect(screen.getByText(/1\.1s/)).toBeInTheDocument();
  });

  it("shows token cost when provided", () => {
    const data: RunSummaryData = {
      ...baseData,
      total_token_cost: 4200,
    };
    render(<RunSummary summary={data} />);
    expect(screen.getByText(/4,200 tokens/)).toBeInTheDocument();
  });

  it("omits token cost when not provided", () => {
    render(<RunSummary summary={baseData} />);
    expect(screen.queryByText(/tokens/)).toBeNull();
  });
});
